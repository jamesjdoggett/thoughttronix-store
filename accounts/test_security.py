"""Security overview and legacy account adoption coverage."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import SecurityRequest, User
from accounts.verification import verification_token, verify_token
from orders.models import Order

pytestmark = pytest.mark.django_db


def correct(client, email=" New+tag@Example.com ", password="customer123", **extra):
    return client.post(
        reverse("accounts:email_correction"),
        {
            "email": email,
            "current_password": password,
            **extra,
        },
        follow=True,
    )


@pytest.mark.parametrize(
    "staff,superuser", [(False, False), (True, False), (True, True)]
)
def test_roles_adopt_email(client, customer, mailoutbox, staff, superuser):
    customer.is_staff = staff
    customer.is_superuser = superuser
    customer.save()
    response = client.post(
        reverse("accounts:login"),
        {
            "username": customer.username,
            "password": "customer123",
        },
        follow=True,
    )
    assert "Add or verify your email in Account security" in response.content.decode()
    assert reverse("accounts:security") in response.content.decode()
    page = client.get(reverse("accounts:security")).content.decode()
    assert "No email address added" in page
    assert "Unverified" in page and "Password" in page
    response = correct(client)
    customer.refresh_from_db()
    assert customer.email == "new+tag@example.com"
    assert not customer.email_verified
    assert "Email address saved" in response.content.decode()
    assert mailoutbox[0].to == [customer.email]
    assert verify_token(verification_token(customer)).pk == customer.pk
    assert "Verified" in client.get(reverse("accounts:security")).content.decode()


@pytest.mark.parametrize("name", ["security", "email_correction"])
@pytest.mark.parametrize("method", ["get", "post"])
def test_controls_require_login(client, name, method):
    response = getattr(client, method)(reverse(f"accounts:{name}"))
    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


@pytest.mark.parametrize("email", ["", "invalid", " OWNER@example.com "])
def test_invalid_and_unavailable_email(client, customer, email, mailoutbox):
    User.objects.create_user(username="owner", email="owner@example.com")
    client.force_login(customer)
    response = correct(client, email=email)
    assert response.context["form"].errors["email"]
    customer.refresh_from_db()
    assert customer.email == ""
    assert not mailoutbox


def test_password_and_ownership(client, customer, staff_user, mailoutbox):
    client.force_login(customer)
    response = correct(client, password="wrong")
    assert response.context["form"].errors["current_password"]
    assert not mailoutbox
    correct(client, user=staff_user.pk, pk=staff_user.pk)
    customer.refresh_from_db()
    staff_user.refresh_from_db()
    assert customer.email == "new+tag@example.com"
    assert staff_user.email == ""
    assert not staff_user.email_verified


@pytest.mark.parametrize("legacy", ["bad-address", "Duplicate@Example.com"])
def test_legacy_evidence_retained_and_correctable(client, customer, legacy):
    customer.legacy_email = legacy
    customer.save()
    client.force_login(customer)
    assert (
        "Add a valid available email"
        in client.get(reverse("accounts:security")).content.decode()
    )
    assert verify_token(verification_token(customer)) is None
    correct(client)
    customer.refresh_from_db()
    assert customer.legacy_email == legacy
    assert customer.email == "new+tag@example.com"


def test_invalid_assigned_address_cannot_verify(client, customer, mailoutbox):
    customer.email = "invalid"
    customer.save()
    assert verify_token(verification_token(customer)) is None
    client.force_login(customer)
    assert (
        "Send verification email"
        not in client.get(reverse("accounts:verification_request")).content.decode()
    )
    client.post(reverse("accounts:verification_request"))
    assert not mailoutbox
    correct(client)
    customer.refresh_from_db()
    assert customer.can_verify_email()


def test_correction_invalidates_old_links_even_after_return(client, customer):
    customer.email = "old@example.com"
    customer.save()
    old_token = verification_token(customer)
    client.force_login(customer)
    correct(client)
    assert verify_token(old_token) is None
    correct(client, email="old@example.com")
    assert verify_token(old_token) is None
    customer.refresh_from_db()
    assert verify_token(verification_token(customer)) is not None


def test_delivery_failure_preserves_correction_and_retry(client, customer, mailoutbox):
    client.force_login(customer)
    with patch("accounts.verification.send_mail", side_effect=OSError("offline")):
        response = correct(client)
    assert "Email delivery failed" in response.content.decode()
    customer.refresh_from_db()
    assert customer.email == "new+tag@example.com"
    response = client.post(reverse("accounts:verification_request"), follow=True)
    assert "Please wait" in response.content.decode()
    SecurityRequest.objects.filter(kind__in=["account", "destination"]).update(
        created_at=timezone.now() - timedelta(seconds=61),
    )
    client.post(reverse("accounts:verification_request"))
    assert len(mailoutbox) == 1


def test_correction_limits_cannot_be_bypassed(client, customer, mailoutbox, settings):
    client.force_login(customer)
    correct(client)
    correct(client, email="another@example.com")
    assert len(mailoutbox) == 1
    settings.SECURITY_EMAIL_NETWORK_LIMIT = 2
    response = correct(client, email="third@example.com")
    assert "network email request limits" in response.content.decode()
    assert len(mailoutbox) == 1
    assert SecurityRequest.objects.filter(kind="network").count() == 3
    customer.refresh_from_db()
    assert customer.email == "third@example.com"


def test_verified_address_cannot_be_corrected(client, customer, mailoutbox):
    customer.email = "verified@example.com"
    customer.email_verified = True
    customer.save()
    client.force_login(customer)
    response = correct(client)
    assert response.context["form"].non_field_errors()
    customer.refresh_from_db()
    assert customer.email == "verified@example.com"
    assert customer.email_verified
    assert not mailoutbox


def test_correction_preserves_account_cart_and_purchases(client, customer, cart_item):
    order = Order.objects.create(
        user=customer, email="historic@example.com", total="12.00"
    )
    password_hash = customer.password
    client.force_login(customer)
    correct(client)
    customer.refresh_from_db()
    cart_item.refresh_from_db()
    order.refresh_from_db()
    assert customer.password == password_hash
    assert cart_item.cart.user_id == customer.pk and cart_item.quantity == 2
    assert order.user_id == customer.pk and order.email == "historic@example.com"
    assert client.get(reverse("orders:history")).status_code == 200
    assert client.get(reverse("orders:cart")).status_code == 200


def test_concurrent_claim_conflict_shows_error(client, customer):
    from django.db import IntegrityError

    client.force_login(customer)
    with patch.object(User, "correct_unverified_email", side_effect=IntegrityError):
        response = correct(client)
    assert response.context["form"].errors["email"] == ["This email is unavailable"]
    customer.refresh_from_db()
    assert customer.email == ""
