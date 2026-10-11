"""Replacement lifecycle, ownership, and atomic claim coverage."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.db import close_old_connections
from django.test import TestCase
from django.urls import reverse

from accounts.models import SecurityRequest, SecurityRequestLock, User
from accounts.verification import verification_token, verify_email_link

pytestmark = pytest.mark.django_db


def prepare(customer):
    customer.email = "old@example.com"
    customer.email_verified = True
    customer.save()
    return customer


def request_change(client, email=" New+tag@Example.com ", password="customer123"):
    return client.post(
        reverse("accounts:email_replacement"),
        {
            "email": email,
            "current_password": password,
        },
        follow=True,
    )


@pytest.mark.parametrize(
    "staff,superuser", [(False, False), (True, False), (True, True)]
)
def test_complete_lifecycle(client, customer, mailoutbox, staff, superuser):
    prepare(customer)
    customer.is_staff, customer.is_superuser = staff, superuser
    customer.save()
    client.force_login(customer)
    old_verification = verification_token(customer)
    old_reset = default_token_generator.make_token(customer)
    response = request_change(client)
    customer.refresh_from_db()
    assert customer.email == "old@example.com" and customer.email_verified
    assert customer.pending_email == "new+tag@example.com"
    assert customer.can_verify_email()
    assert "Pending replacement" in response.content.decode()
    assert mailoutbox[0].to == [customer.pending_email]
    with TestCase.captureOnCommitCallbacks(execute=True):
        result = verify_email_link(verification_token(customer))
    assert result.status == "verified"
    customer.refresh_from_db()
    assert customer.email == "new+tag@example.com" and customer.email_verified
    assert customer.pending_email == ""
    assert mailoutbox[-1].to == ["old@example.com"]
    assert "http" not in mailoutbox[-1].body
    assert verify_email_link(old_verification).status == "superseded"
    assert not default_token_generator.check_token(customer, old_reset)
    assert client.get(reverse("accounts:security")).status_code == 200


def test_validation_and_isolation(client, customer, staff_user, mailoutbox):
    prepare(customer)
    client.force_login(customer)
    for email, password in [
        ("x@example.com", "wrong"),
        ("old@example.com", "customer123"),
        ("invalid", "customer123"),
    ]:
        assert request_change(client, email, password).context["form"].errors
    staff_user.email = "used@example.com"
    staff_user.save()
    assert request_change(client, " USED@example.com ").context["form"].errors
    assert not mailoutbox
    client.post(
        reverse("accounts:email_replacement"),
        {
            "email": "new@example.com",
            "current_password": "customer123",
            "user": staff_user.pk,
        },
    )
    staff_user.refresh_from_db()
    assert not staff_user.pending_email


def test_cancel_replace_failure_and_shared_limits(client, customer, mailoutbox):
    prepare(customer)
    client.force_login(customer)
    with patch("accounts.verification.send_mail", side_effect=OSError):
        response = request_change(client)
    assert "Email delivery failed" in response.content.decode()
    customer.refresh_from_db()
    first = verification_token(customer)
    assert customer.pending_email
    response = client.post(reverse("accounts:verification_request"), follow=True)
    assert "cooldown" in response.content.decode()
    assert not mailoutbox
    request_change(client, "other@example.com")
    customer.refresh_from_db()
    second = verification_token(customer)
    assert verify_email_link(first).status == "superseded"
    assert SecurityRequest.objects.filter(kind="account").count() == 1
    client.post(reverse("accounts:email_replacement_cancel"))
    customer.refresh_from_db()
    assert customer.pending_email == "" and customer.email_verified
    assert verify_email_link(second).status == "superseded"


def test_unverified_and_anonymous_cannot_replace(client, customer):
    for name in ["email_replacement", "email_replacement_cancel"]:
        assert client.post(reverse("accounts:" + name)).status_code == 302
    client.force_login(customer)
    assert request_change(client).context["form"].errors
    customer.refresh_from_db()
    assert not customer.pending_email


def test_expiry_retry_and_notification_failure(client, customer):
    prepare(customer)
    customer.stage_email_replacement("new@example.com")
    with patch("django.core.signing.time.time", return_value=1000):
        token = verification_token(customer)
    with patch("django.core.signing.time.time", return_value=87401):
        assert verify_email_link(token).status == "expired"
    customer.refresh_from_db()
    assert customer.pending_email == "new@example.com"
    client.force_login(customer)
    response = client.post(reverse("accounts:verification_request"), follow=True)
    assert "Verification email sent" in response.content.decode()
    with patch("accounts.verification.send_mail", side_effect=OSError):
        with TestCase.captureOnCommitCallbacks(execute=True):
            assert verify_email_link(verification_token(customer)).status == "verified"
    customer.refresh_from_db()
    assert customer.email == "new@example.com" and not customer.pending_email


@pytest.mark.django_db(transaction=True)
def test_competing_claims_are_atomic():
    users = [
        User.objects.create_user(
            username=f"claim{i}", email=f"old{i}@example.com", email_verified=True
        )
        for i in range(2)
    ]
    for user in users:
        assert user.stage_email_replacement("shared@example.com")
    tokens = [verification_token(user) for user in users]
    SecurityRequestLock.objects.get_or_create(pk=1)
    barrier = Barrier(2)

    def claim(token):
        close_old_connections()
        try:
            barrier.wait()
            return verify_email_link(token).status
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(claim, tokens)) == ["unavailable", "verified"]
    assert User.objects.filter(email="shared@example.com").count() == 1
    loser = User.objects.exclude(email="shared@example.com").get()
    assert loser.email_verified and loser.pending_email == "shared@example.com"


def test_pending_keeps_checkout_and_recovery(client, customer, cart_item):
    prepare(customer)
    client.force_login(customer)
    reset = default_token_generator.make_token(customer)
    customer.stage_email_replacement("new@example.com")
    response = client.get(reverse("orders:checkout"))
    assert response.status_code == 200
    customer.refresh_from_db()
    assert default_token_generator.check_token(customer, reset)
    assert customer.email == "old@example.com"
    assert cart_item.cart.items.count() == 1
