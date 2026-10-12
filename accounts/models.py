from dataclasses import dataclass
from datetime import timedelta
from math import ceil
from time import sleep

from django.conf import settings
from django.contrib.auth import password_validation
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import OperationalError, models, transaction
from django.db.models import F
from django.db.models.functions import Lower, Trim
from django.utils import timezone


@dataclass(frozen=True)
class SecurityRequestDecision:
    """A reservation outcome with actionable, non-secret retry feedback."""

    allowed: bool
    reason: str = ""
    retry_after: int = 0

    def __bool__(self) -> bool:
        return self.allowed

    @property
    def message(self) -> str:
        """Explain suppression without revealing another account's identity."""
        if self.reason == "verified":
            return "Your email is already verified. No new email is needed."
        if self.reason == "address":
            return "Add or correct your email in Account security before requesting verification."
        labels = {
            "network": "network email request limits",
            "signup": "signup attempt limits",
            "account_hour": "the five-per-hour account email limit",
            "destination_hour": "the five-per-hour destination email limit",
            "account_cooldown": "the account email cooldown",
            "destination_cooldown": "the destination email cooldown",
        }
        unit = "second" if self.retry_after == 1 else "seconds"
        return (
            f"Please wait {self.retry_after} {unit} before retrying because of "
            f"{labels.get(self.reason, 'email request limits')}. "
            "Retry from Verify email after this wait; repeated requests may extend network waits."
        )


class User(AbstractUser):
    """The store's user model.

    Roles use Django's own vocabulary and nothing else: customers are
    plain users, employees are ``is_staff``, the admin is ``is_superuser``.
    """

    # Nullable per the PRD: an absent job title is unknown, not empty.
    job_title = models.CharField(max_length=150, null=True, blank=True)  # noqa: DJ001

    email_verified = models.BooleanField(default=False)
    email_revision = models.PositiveBigIntegerField(default=0)
    pending_email = models.EmailField(blank=True)
    pending_email_revision = models.PositiveBigIntegerField(default=0)
    legacy_email = models.TextField(blank=True, editable=False)

    class Meta(AbstractUser.Meta):
        constraints = [
            models.UniqueConstraint(
                Lower(Trim("email")),
                condition=~models.Q(email=""),
                name="accounts_unique_normalized_email",
            )
        ]

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def can_verify_email(self):
        """Require a valid, uniquely assigned current address."""
        try:
            validate_email(self.email)
        except ValidationError:
            return False
        return (
            not User.objects.exclude(pk=self.pk)
            .filter(email__iexact=self.email.strip().lower())
            .exists()
        )

    def correct_unverified_email(self, email):
        """Claim an address only while the authenticated account remains unverified."""
        updated = User.objects.filter(
            pk=self.pk,
            email_verified=False,
            email_revision=self.email_revision,
            password=self.password,
        ).update(email=email, email_revision=F("email_revision") + 1)
        self.refresh_from_db()
        return bool(updated)

    def reset_recovered_password(self, password: str) -> bool:
        """Consume the observed credentials atomically and cancel pending replacement."""
        old_password = self.password
        self.set_password(password)
        updated = User.objects.filter(
            pk=self.pk,
            password=old_password,
            email_revision=self.email_revision,
            email=self.email,
            email_verified=True,
            is_active=True,
        ).update(
            password=self.password,
            pending_email="",
            pending_email_revision=F("pending_email_revision") + 1,
        )
        if updated:
            self.refresh_from_db()
            password_validation.password_changed(password, self)
            self._password = None
        return bool(updated)

    def stage_email_replacement(self, email):
        """Replace or cancel only the pending request the caller observed."""
        updated = User.objects.filter(
            pk=self.pk,
            email_verified=True,
            password=self.password,
            email_revision=self.email_revision,
            pending_email_revision=self.pending_email_revision,
        ).update(
            pending_email=email, pending_email_revision=F("pending_email_revision") + 1
        )
        self.refresh_from_db()
        return bool(updated)


class SecurityRequestLock(models.Model):
    """A singleton database mutex serializes security request reservations."""

    revision = models.PositiveBigIntegerField(default=0)

    def __str__(self):
        return "Security request mutex"


class SecurityRequestManager(models.Manager):
    """Serialize rate reservations across workers using a database write lock."""

    def reserve(
        self,
        network,
        *,
        signup=False,
        user=None,
        count_network=True,
        network_only=False,
        pending=False,
        recovery=False,
    ):
        """Retain the boolean reservation API for existing callers."""
        return bool(
            self.reserve_result(
                network,
                signup=signup,
                user=user,
                count_network=count_network,
                network_only=network_only,
                pending=pending,
                recovery=recovery,
            )
        )

    def reserve_result(
        self,
        network: str,
        *,
        signup: bool = False,
        user: User | None = None,
        count_network: bool = True,
        network_only: bool = False,
        pending: bool = False,
        recovery: bool = False,
    ) -> SecurityRequestDecision:
        """Retry transient SQLite lock contention without allowing extra sends."""
        for attempt in range(100):
            try:
                return self._reserve(
                    network,
                    signup=signup,
                    user=user,
                    count_network=count_network,
                    network_only=network_only,
                    pending=pending,
                    recovery=recovery,
                )
            except OperationalError as error:
                if "locked" not in str(error).lower() or attempt == 99:
                    raise
                sleep(0.01)

    def _reserve(
        self,
        network,
        *,
        signup=False,
        user=None,
        count_network=True,
        network_only=False,
        pending=False,
        recovery=False,
    ):
        with transaction.atomic():
            updated = SecurityRequestLock.objects.filter(pk=1).update(
                revision=F("revision") + 1
            )
            if not updated:
                SecurityRequestLock.objects.create(pk=1)
            now = timezone.now()
            recent = SecurityRequest.objects.filter(
                created_at__gt=now - timedelta(hours=1)
            )
            count = recent.filter(kind="network", key=network).count()
            if count_network:
                SecurityRequest.objects.create(
                    kind="network", key=network, created_at=now
                )
            if count_network and count >= settings.SECURITY_EMAIL_NETWORK_LIMIT:
                return self._wait(
                    recent.filter(kind="network", key=network),
                    settings.SECURITY_EMAIL_NETWORK_LIMIT,
                    now,
                    "network",
                )
            if network_only:
                return SecurityRequestDecision(True)
            if signup:
                count = recent.filter(kind="signup", key=network).count()
                SecurityRequest.objects.create(
                    kind="signup", key=network, created_at=now
                )
                if count >= settings.SECURITY_SIGNUP_LIMIT:
                    return self._wait(
                        recent.filter(kind="signup", key=network),
                        settings.SECURITY_SIGNUP_LIMIT,
                        now,
                        "signup",
                    )
                return SecurityRequestDecision(True)
            if user is not None:
                user.refresh_from_db()
            if (
                user is not None
                and user.email_verified
                and not pending
                and not recovery
            ):
                return SecurityRequestDecision(False, "verified")
            if (
                user is None
                or (recovery and (not user.email_verified or not user.is_active))
                or (not pending and not user.can_verify_email())
                or (pending and (not user.email_verified or not user.pending_email))
            ):
                return SecurityRequestDecision(False, "address")
            keys = [
                ("account", str(user.pk)),
                (
                    "destination",
                    (user.pending_email if pending else user.email).strip().lower(),
                ),
            ]
            waits = []
            for kind, key in keys:
                attempts = recent.filter(kind=kind, key=key)
                if attempts.count() >= 5:
                    waits.append(self._wait(attempts, 5, now, f"{kind}_hour"))
                last = attempts.order_by("-created_at").first()
                if last and last.created_at > now - timedelta(seconds=60):
                    waits.append(
                        SecurityRequestDecision(
                            False,
                            f"{kind}_cooldown",
                            ceil(
                                (
                                    last.created_at + timedelta(seconds=60) - now
                                ).total_seconds()
                            ),
                        )
                    )
            if waits:
                return max(waits, key=lambda decision: decision.retry_after)
            for kind, key in keys:
                SecurityRequest.objects.create(kind=kind, key=key, created_at=now)
            return SecurityRequestDecision(True)

    def _wait(self, attempts, limit, now, reason):
        # Suppressed network/signup attempts count too, including this request.
        dates = list(
            attempts.order_by("created_at").values_list("created_at", flat=True)
        )
        release = dates[max(0, len(dates) - limit)] if limit > 0 else now
        return SecurityRequestDecision(
            False,
            reason,
            max(1, ceil((release + timedelta(hours=1) - now).total_seconds())),
        )


class SecurityRequest(models.Model):
    """Durable request and attempted-send accounting, including failures."""

    kind = models.CharField(max_length=16)
    key = models.CharField(max_length=254)
    created_at = models.DateTimeField()

    objects = SecurityRequestManager()

    class Meta:
        indexes = [models.Index(fields=["kind", "key", "created_at"])]

    def __str__(self):
        return f"{self.kind}: {self.key}"
