"""Initial email ownership and durable request reservations."""

import logging

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.db import transaction
from django.http import HttpRequest
from django.urls import reverse

from .models import SecurityRequest, User

logger = logging.getLogger(__name__)
SALT = "accounts.initial-email"


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
    try:
        data = signing.loads(token, salt=SALT, max_age=86400)
    except signing.BadSignature:
        return None
    with transaction.atomic():
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
            return None
        user.email_verified = True
        user.save(update_fields=["email_verified"])
        return user


def send_verification(
    request: HttpRequest, user: User, *, count_network: bool = True
) -> str:
    """Reserve a send and report delivery failures without deleting the account."""
    if not reserve_request(
        request.META.get("REMOTE_ADDR", "unknown"),
        user=user,
        count_network=count_network,
    ):
        return "Please wait before retrying. Sends are limited to once per minute and five per hour; network limits also apply."
    link = request.build_absolute_uri(
        reverse("accounts:verify_email", args=[verification_token(user)])
    )
    try:
        send_mail(
            "Verify your ThoughtTronix email",
            f"Verify your email within 24 hours: {link}\nThis link does not sign you in.",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
        )
    except Exception:
        logger.exception("Verification email delivery failed for account %s", user.pk)
        return "Email delivery failed. Your account is saved. Sign in and retry from Verify email after one minute."
    return "Verification email sent. Check your inbox; the link expires in 24 hours."
