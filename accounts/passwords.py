"""Password security notifications independent of credential persistence."""

import logging

from django.conf import settings
from django.core.mail import send_mail

from .models import User

logger = logging.getLogger(__name__)


def send_password_change_alert(user: User) -> None:
    """Notify only the verified current address; delivery cannot undo a change."""
    if not user.email_verified or not user.can_verify_email():
        return
    try:
        if not send_mail(
            "Your ThoughtTronix password changed",
            "Your account password was changed. If you did not request this, review your account security.",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
        ):
            raise OSError("Email backend did not accept the message")
    except Exception:
        logger.exception("Password change notification failed for account %s", user.pk)
