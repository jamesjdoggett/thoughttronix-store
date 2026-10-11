"""Initial email ownership and durable request reservations."""

import logging
from dataclasses import dataclass
from time import sleep

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.db import OperationalError, transaction
from django.db.models import F
from django.http import HttpRequest
from django.urls import reverse

from .models import SecurityRequest, SecurityRequestLock, User

logger = logging.getLogger(__name__)
SALT = "accounts.initial-email"


@dataclass(frozen=True)
class VerificationResult:
    """Public link feedback without exposing an account or address."""

    status: str
    user: User | None = None

    @property
    def message(self) -> str:
        """Describe the link's outcome and the next available action."""
        return {
            "verified": "Email verified.",
            "already_verified": "This email is already verified. You do not need another link.",
            "expired": "This verification link has expired after 24 hours. Sign in to the account that requested it to send another email.",
            "superseded": "This verification link was invalidated by an email correction or is no longer available. Sign in and verify your current address.",
            "invalid": "This link is invalid or expired. Copy the complete link from your email, or sign in to the account that requested it to send another email.",
        }[self.status]


def reserve_request(
    network: str,
    *,
    signup: bool = False,
    user: User | None = None,
    count_network: bool = True,
    network_only: bool = False,
) -> bool:
    """Reserve security requests through the durable model manager."""
    return SecurityRequest.objects.reserve(
        network,
        signup=signup,
        user=user,
        count_network=count_network,
        network_only=network_only,
    )


def verification_token(user: User) -> str:
    """Sign an account and its current address with Django's timestamp signer."""
    return signing.dumps(
        {"user": user.pk, "email": user.email, "revision": user.email_revision},
        salt=SALT,
    )


def verify_token(token: str) -> User | None:
    """Verify only the signed current address, within twenty-four hours."""
    return verify_email_link(token).user


def verify_email_link(token: str) -> VerificationResult:
    """Validate signed payloads and serialize verification against corrections."""
    try:
        data = signing.loads(token, salt=SALT, max_age=86400)
    except signing.SignatureExpired:
        return VerificationResult("expired")
    except (signing.BadSignature, ValueError, TypeError, UnicodeError):
        return VerificationResult("invalid")
    if (
        not isinstance(data, dict)
        or type(data.get("user")) is not int
        or not 0 < data["user"] <= 9223372036854775807
        or not isinstance(data.get("email"), str)
        or type(data.get("revision", 0)) is not int
        or not 0 <= data.get("revision", 0) <= 9223372036854775807
    ):
        return VerificationResult("invalid")
    for attempt in range(100):
        try:
            return _verify_address(data)
        except OperationalError as error:
            if "locked" not in str(error).lower() or attempt == 99:
                raise
            sleep(0.01)


def _verify_address(data):
    with transaction.atomic():
        # SQLite's select_for_update is a no-op: take a write lock before reading.
        updated = SecurityRequestLock.objects.filter(pk=1).update(
            revision=F("revision") + 1
        )
        if not updated:
            SecurityRequestLock.objects.create(pk=1)
        user = (
            User.objects.select_for_update()
            .filter(
                pk=data["user"],
                email=data["email"],
                email_revision=data.get("revision", 0),
            )
            .first()
        )
        if user is None or not user.can_verify_email():
            return VerificationResult("superseded")
        if user.email_verified:
            return VerificationResult("already_verified", user)
        user.email_verified = True
        user.save(update_fields=["email_verified"])
        return VerificationResult("verified", user)


def send_verification(
    request: HttpRequest, user: User, *, count_network: bool = True
) -> str:
    """Reserve a send and report delivery failures without deleting the account."""
    decision = SecurityRequest.objects.reserve_result(
        request.META.get("REMOTE_ADDR", "unknown"),
        user=user,
        count_network=count_network,
    )
    if not decision:
        return decision.message
    link = request.build_absolute_uri(
        reverse("accounts:verify_email", args=[verification_token(user)])
    )
    try:
        sent = send_mail(
            "Verify your ThoughtTronix email",
            f"Verify your email within 24 hours: {link}\nThis link does not sign you in.",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
        )
        if not sent:
            raise OSError("Email backend did not accept the message")
    except Exception:
        logger.exception("Verification email delivery failed for account %s", user.pk)
        return "Email delivery failed. Your email address and account are saved. Retry from Verify email after 60 seconds; hourly and network limits still apply."
    return "Verification email sent. Check your inbox; the link expires in 24 hours."
