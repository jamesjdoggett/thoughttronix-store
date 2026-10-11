from datetime import timedelta
from time import sleep

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import OperationalError, models, transaction
from django.db.models import F
from django.db.models.functions import Lower, Trim
from django.utils import timezone


class User(AbstractUser):
    """The store's user model.

    Roles use Django's own vocabulary and nothing else: customers are
    plain users, employees are ``is_staff``, the admin is ``is_superuser``.
    """

    # Nullable per the PRD: an absent job title is unknown, not empty.
    job_title = models.CharField(max_length=150, null=True, blank=True)  # noqa: DJ001

    email_verified = models.BooleanField(default=False)
    email_revision = models.PositiveBigIntegerField(default=0)
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
    ):
        """Retry transient SQLite lock contention without allowing extra sends."""
        for attempt in range(100):
            try:
                return self._reserve(
                    network,
                    signup=signup,
                    user=user,
                    count_network=count_network,
                    network_only=network_only,
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
    ):
        now = timezone.now()
        with transaction.atomic():
            updated = SecurityRequestLock.objects.filter(pk=1).update(
                revision=F("revision") + 1
            )
            if not updated:
                SecurityRequestLock.objects.create(pk=1)
            recent = SecurityRequest.objects.filter(
                created_at__gt=now - timedelta(hours=1)
            )
            count = recent.filter(kind="network", key=network).count()
            if count_network:
                SecurityRequest.objects.create(
                    kind="network", key=network, created_at=now
                )
            if count_network and count >= settings.SECURITY_EMAIL_NETWORK_LIMIT:
                return False
            if network_only:
                return True
            if signup:
                count = recent.filter(kind="signup", key=network).count()
                SecurityRequest.objects.create(
                    kind="signup", key=network, created_at=now
                )
                return count < settings.SECURITY_SIGNUP_LIMIT
            if user is None or user.email_verified or not user.can_verify_email():
                return False
            try:
                validate_email(user.email)
            except ValidationError:
                return False
            keys = [
                ("account", str(user.pk)),
                ("destination", user.email.strip().lower()),
            ]
            for kind, key in keys:
                attempts = recent.filter(kind=kind, key=key)
                if (
                    attempts.count() >= 5
                    or attempts.filter(
                        created_at__gt=now - timedelta(seconds=60)
                    ).exists()
                ):
                    return False
            for kind, key in keys:
                SecurityRequest.objects.create(kind=kind, key=key, created_at=now)
            return True


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
