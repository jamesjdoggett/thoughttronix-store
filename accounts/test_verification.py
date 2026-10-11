"""Phase 1 signup, email ownership, and request-limit regression coverage."""

import io
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from time import sleep
from unittest.mock import patch
from urllib.parse import urlsplit

import pytest
from django.db import (
    IntegrityError,
    OperationalError,
    close_old_connections,
    transaction,
)
from django.urls import reverse
from django.utils import timezone

from accounts.models import SecurityRequest, SecurityRequestLock, User
from accounts.verification import reserve_request, verification_token, verify_token

pytestmark = pytest.mark.django_db


def signup(client, **changes):
    data = dict(
        username="new-user",
        email=" New+tag@Example.com ",
        password1="neural-implant-9000",
        password2="neural-implant-9000",
    )
    data.update(changes)
    return client.post(reverse("accounts:signup"), data, follow=True)


def test_signup_mail_and_no_automatic_login(client, mailoutbox):
    response = signup(client)
    user = User.objects.get(username="new-user")
    assert user.email == "new+tag@example.com"
    assert not user.email_verified
    assert not response.context["user"].is_authenticated
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == [user.email]
    assert "/accounts/verify/" in mailoutbox[0].body
    assert SecurityRequest.objects.filter(kind="network").count() == 1


@pytest.mark.parametrize("email", ["", "invalid", " NEW+TAG@example.com "])
def test_required_valid_unique_email(client, email):
    User.objects.create_user(username="existing", email="new+tag@example.com")
    response = signup(client, email=email)
    assert response.context["form"].errors["email"]
    assert not User.objects.filter(username="new-user").exists()
    assert "Password recovery will be available" in response.content.decode()


def test_dots_and_plus_remain_significant(client):
    User.objects.create_user(username="existing", email="newtag@example.com")
    signup(client)
    assert User.objects.filter(email="new+tag@example.com").exists()


def test_database_rejects_normalized_duplicate():
    User.objects.create_user(username="one", email="identity@example.com")
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.bulk_create([User(username="two", email=" IDENTITY@example.com ")])


def test_verification_bound_to_address_and_no_login(client, customer):
    customer.email = "owner@example.com"
    customer.save()
    token = verification_token(customer)
    response = client.get(reverse("accounts:verify_email", args=[token]))
    customer.refresh_from_db()
    assert customer.email_verified
    assert not response.context["user"].is_authenticated
    assert "Sign in to your account" in response.content.decode()
    customer.email = "changed@example.com"
    customer.email_verified = False
    customer.save()
    assert verify_token(token) is None


def test_matching_and_other_signed_in_accounts(client, customer, staff_user):
    customer.email = "owner@example.com"
    customer.save()
    token = verification_token(customer)
    client.force_login(staff_user)
    response = client.get(reverse("accounts:verify_email", args=[token]))
    staff_user.refresh_from_db()
    assert not staff_user.email_verified
    assert "Sign in to your account" in response.content.decode()
    client.force_login(customer)
    response = client.get(reverse("accounts:verify_email", args=[token]))
    assert "Continue shopping" in response.content.decode()


def test_invalid_and_expired_links(client, customer):
    customer.email = "owner@example.com"
    customer.save()
    with patch("django.core.signing.time.time", return_value=100000):
        token = verification_token(customer)
    with patch("django.core.signing.time.time", return_value=186401):
        assert verify_token(token) is None
    response = client.get(reverse("accounts:verify_email", args=["broken"]))
    assert "invalid or expired" in response.content.decode()
    assert reverse("accounts:verification_request") in response.content.decode()
    customer.refresh_from_db()
    assert not customer.email_verified


def test_failure_preserves_account_and_retry(client, mailoutbox):
    with patch("accounts.verification.send_mail", side_effect=OSError("offline")):
        response = signup(client)
    user = User.objects.get(username="new-user")
    assert "Email delivery failed" in response.content.decode()
    client.force_login(user)
    response = client.post(reverse("accounts:verification_request"), follow=True)
    assert "Please wait" in response.content.decode()
    SecurityRequest.objects.filter(kind__in=["account", "destination"]).update(
        created_at=timezone.now() - timedelta(seconds=61)
    )
    response = client.post(reverse("accounts:verification_request"), follow=True)
    assert "Verification email sent" in response.content.decode()
    assert len(mailoutbox) == 1
    assert User.objects.filter(username="new-user").count() == 1


def test_resends_keep_earlier_links_valid_and_require_login(client, customer):
    assert client.get(reverse("accounts:verification_request")).status_code == 302
    customer.email = "owner@example.com"
    customer.save()
    token = verification_token(customer)
    client.force_login(customer)
    client.post(reverse("accounts:verification_request"))
    assert verify_token(token).pk == customer.pk


def test_cooldown_and_hourly_limits(customer):
    customer.email = "owner@example.com"
    customer.save()
    now = timezone.now()
    for index in range(5):
        with patch(
            "accounts.models.timezone.now",
            return_value=now + timedelta(seconds=60 * index),
        ):
            assert reserve_request("network", user=customer)
            assert not reserve_request("other-network", user=customer)
    with patch(
        "accounts.models.timezone.now", return_value=now + timedelta(seconds=300)
    ):
        assert not reserve_request("network", user=customer)
    with patch("accounts.models.timezone.now", return_value=now + timedelta(hours=1)):
        assert reserve_request("network", user=customer)


def test_network_counts_suppressed_requests(customer, settings):
    settings.SECURITY_EMAIL_NETWORK_LIMIT = 2
    assert not reserve_request("network", user=customer)
    assert not reserve_request("network", user=customer)
    customer.email = "owner@example.com"
    customer.save()
    assert not reserve_request("network", user=customer)
    assert SecurityRequest.objects.filter(kind="network").count() == 3
    assert not SecurityRequest.objects.filter(kind="account").exists()


def test_signup_attempt_limit(client, settings):
    settings.SECURITY_SIGNUP_LIMIT = 2
    signup(client, email="invalid")
    signup(client, email="invalid")
    response = signup(client)
    assert "Too many signup attempts" in response.content.decode()
    assert not User.objects.filter(username="new-user").exists()


def test_unverified_login_catalog_cart_and_history(client, customer, product):
    response = client.post(
        reverse("accounts:login"), {"username": "customer", "password": "customer123"}
    )
    assert response.status_code == 302
    assert client.get(reverse("products:catalog")).status_code == 200
    assert client.post(reverse("orders:add", args=[product.pk])).status_code == 200
    assert client.get(reverse("orders:cart")).status_code == 200
    assert client.get(reverse("orders:history")).status_code == 200


@pytest.mark.django_db(transaction=True)
def test_concurrent_reservations_cannot_bypass_cooldown():
    user = User.objects.create_user(username="concurrent", email="owner@example.com")
    SecurityRequestLock.objects.get_or_create(pk=1)

    def attempt(_):
        close_old_connections()
        try:
            return reserve_request("network", user=user)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, range(2)))
    assert sorted(outcomes) == [False, True]
    assert SecurityRequest.objects.filter(kind="account").count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_signup_email_claims_have_only_one_winner():
    barrier = Barrier(2)

    def claim(index):
        close_old_connections()
        barrier.wait()
        try:
            for attempt in range(100):
                try:
                    User.objects.create_user(
                        username=f"claim-{index}",
                        email=" SAME@example.com " if index else "same@example.com",
                    )
                    return True
                except IntegrityError:
                    return False
                except OperationalError as error:
                    if "locked" not in str(error).lower() or attempt == 99:
                        raise
                    sleep(0.01)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(claim, range(2)))
    assert sorted(outcomes) == [False, True]
    assert User.objects.filter(email="same@example.com").count() == 1


@pytest.mark.parametrize("password", ["tiny", "123456789", "password"])
def test_signup_keeps_django_password_policy(client, password):
    response = signup(client, password1=password, password2=password)
    assert response.context["form"].errors["password2"]
    assert not User.objects.filter(username="new-user").exists()


def test_destination_limit_shared_with_account_requests(customer):
    customer.email = "owner@example.com"
    customer.save()
    SecurityRequest.objects.create(
        kind="destination", key=customer.email, created_at=timezone.now()
    )
    assert not reserve_request("different-network", user=customer)
    assert not SecurityRequest.objects.filter(kind="account").exists()


@pytest.mark.parametrize("signed_in", [False, True])
def test_follows_actual_signup_email_link(client, mailoutbox, signed_in):
    signup(client)
    user = User.objects.get(username="new-user")
    assert not user.email_verified
    link = next(word for word in mailoutbox[0].body.split() if word.startswith("http"))
    if signed_in:
        client.force_login(user)
    response = client.get(urlsplit(link).path)
    user.refresh_from_db()
    assert response.context["verified"]
    assert user.email_verified
    assert response.context["user"].is_authenticated == signed_in


@pytest.mark.parametrize("signed_in", [False, True])
def test_follows_actual_console_email_link(client, settings, signed_in):
    settings.EMAIL_BACKEND = "accounts.mail_backends.ConsoleEmailBackend"
    stream = io.StringIO()
    with patch("sys.stdout", stream):
        signup(client)
    user = User.objects.get(username="new-user")
    assert not user.email_verified
    link = next(word for word in stream.getvalue().split() if word.startswith("http"))
    if signed_in:
        client.force_login(user)
    response = client.get(urlsplit(link).path, follow=True)
    user.refresh_from_db()
    assert response.context["verified"]
    assert user.email_verified
    assert response.context["user"].is_authenticated == signed_in


def test_follows_actual_resend_console_email_link(client, customer, settings):
    settings.EMAIL_BACKEND = "accounts.mail_backends.ConsoleEmailBackend"
    customer.email = "owner@example.com"
    customer.save()
    client.force_login(customer)
    stream = io.StringIO()
    with patch("sys.stdout", stream):
        response = client.post(reverse("accounts:verification_request"), follow=True)
    assert "Verification email sent" in response.content.decode()
    link = next(word for word in stream.getvalue().split() if word.startswith("http"))
    response = client.get(urlsplit(link).path)
    customer.refresh_from_db()
    assert response.context["verified"]
    assert response.context["matching_account"]
    assert customer.email_verified
