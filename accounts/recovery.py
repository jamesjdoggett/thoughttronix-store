"""Time-limited recovery links and generic, rate-limited delivery."""

import logging

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.http import HttpRequest
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .models import SecurityRequest, User
from .passwords import send_password_change_alert

logger = logging.getLogger(__name__)


class RecoveryTokenGenerator(PasswordResetTokenGenerator):
    """Use Django token security with PRD-specific invalidation state."""

    def _make_hash_value(self, user, timestamp):
        # Sign-in must not consume a link. Email revisions prevent reactivation
        # when an account later returns to a previously used email address.
        return (
            f"{user.pk}:{user.password}:{timestamp}:{user.email}:{user.email_revision}"
        )


recovery_token_generator = RecoveryTokenGenerator()


def recovery_token(user: User) -> str:
    """Pair the public account identifier with Django's time-limited token."""
    return f"{urlsafe_base64_encode(force_bytes(user.pk))}~{recovery_token_generator.make_token(user)}"


def recovery_user(token: str) -> User | None:
    """Resolve an eligible account using Django's token verification."""
    try:
        uid, secret = token.split("~", 1)
        pk = int(urlsafe_base64_decode(uid).decode())
        if not 0 < pk <= 9223372036854775807:
            return None
    except (ValueError, TypeError, UnicodeError):
        return None
    user = User.objects.filter(pk=pk, is_active=True, email_verified=True).first()
    if (
        user
        and user.has_usable_password()
        and user.can_verify_email()
        and recovery_token_generator.check_token(user, secret)
    ):
        return user
    return None


def send_recovery(request: HttpRequest, email: str) -> None:
    """Count every request and conceal eligibility, suppression, and delivery errors."""
    user = User.objects.filter(
        email__iexact=email.strip().lower(), email_verified=True, is_active=True
    ).first()
    decision = SecurityRequest.objects.reserve_result(
        request.META.get("REMOTE_ADDR", "unknown"), user=user, recovery=True
    )
    if not decision or not user.has_usable_password():
        return
    link = request.build_absolute_uri(
        reverse(
            "accounts:password_reset_confirm", args=recovery_token(user).split("~", 1)
        )
    )
    try:
        if not send_mail(
            "Reset your ThoughtTronix password",
            f"Choose a new password within 24 hours: {link}\nThis link does not sign you in.",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
        ):
            raise OSError("Email backend did not accept the message")
    except Exception:
        logger.exception("Recovery email delivery failed for account %s", user.pk)


def reset_password(user: User, password: str) -> bool:
    """Atomically consume all links, revoke sessions, and cancel pending replacement."""
    updated = user.reset_recovered_password(password)
    if updated:
        send_password_change_alert(user)
    return updated
