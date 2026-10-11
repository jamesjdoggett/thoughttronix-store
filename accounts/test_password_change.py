"""Signed-in password validation, sessions, and notification behavior."""

from unittest.mock import patch

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db
NEW_PASSWORD = "Orbit!Lantern72Quartz"


def change(client, old="customer123", new=NEW_PASSWORD, confirmation=None):
    return client.post(
        reverse("accounts:password_change"),
        {
            "old_password": old,
            "new_password1": new,
            "new_password2": new if confirmation is None else confirmation,
        },
        follow=True,
    )


@pytest.mark.parametrize(
    "staff,superuser", [(False, False), (True, False), (True, True)]
)
@pytest.mark.parametrize("verified", [False, True])
def test_change_sessions_and_alert(
    client, customer, mailoutbox, staff, superuser, verified
):
    customer.email = "current@example.com"
    customer.email_verified = verified
    customer.is_staff, customer.is_superuser = staff, superuser
    customer.pending_email = "pending@example.com" if verified else ""
    customer.save()
    other = Client()
    for session in (client, other):
        assert session.login(username=customer.username, password="customer123")
    reset_token = default_token_generator.make_token(customer)
    response = change(client)
    assert response.status_code == 200
    assert "Password changed." in response.content.decode()
    customer.refresh_from_db()
    assert customer.check_password(NEW_PASSWORD)
    assert not default_token_generator.check_token(customer, reset_token)
    assert client.get(reverse("accounts:security")).status_code == 200
    assert other.get(reverse("accounts:security")).status_code == 302
    assert not other.login(username=customer.username, password="customer123")
    assert other.login(username=customer.username, password=NEW_PASSWORD)
    assert len(mailoutbox) == int(verified)
    if verified:
        assert mailoutbox[0].to == ["current@example.com"]
        content = mailoutbox[0].subject + mailoutbox[0].body
        assert "password changed" in content.lower()
        for secret in ("customer123", NEW_PASSWORD, reset_token, "http"):
            assert secret not in content
        assert customer.pending_email == "pending@example.com"


@pytest.mark.parametrize(
    "old,new,confirmation,field",
    [
        ("wrong", NEW_PASSWORD, NEW_PASSWORD, "old_password"),
        ("customer123", NEW_PASSWORD, "different", "new_password2"),
        ("customer123", "aB!4", "aB!4", "new_password2"),
        ("customer123", "password", "password", "new_password2"),
        ("customer123", "9375612048", "9375612048", "new_password2"),
        ("customer123", "customer", "customer", "new_password2"),
    ],
)
def test_validation_preserves_credentials_and_sessions(
    client, customer, mailoutbox, old, new, confirmation, field
):
    other = Client()
    for session in (client, other):
        session.force_login(customer)
    response = change(client, old, new, confirmation)
    assert field in response.context["form"].errors
    customer.refresh_from_db()
    assert customer.check_password("customer123")
    assert other.get(reverse("accounts:security")).status_code == 200
    assert not mailoutbox


@pytest.mark.parametrize("result", [OSError("unavailable"), 0])
def test_alert_failure_does_not_undo_change(client, customer, result, caplog):
    customer.email = "verified@example.com"
    customer.email_verified = True
    customer.save()
    client.force_login(customer)
    kwargs = (
        {"side_effect": result}
        if isinstance(result, Exception)
        else {"return_value": result}
    )
    with patch("accounts.passwords.send_mail", **kwargs):
        assert change(client).status_code == 200
    customer.refresh_from_db()
    assert customer.check_password(NEW_PASSWORD)
    assert client.get(reverse("accounts:security")).status_code == 200
    assert "Password change notification failed" in caplog.text


def test_anonymous_and_csrf_protection(customer):
    url = reverse("accounts:password_change")
    anonymous = Client()
    assert anonymous.get(url).status_code == 302
    assert anonymous.post(url, {}).status_code == 302
    protected = Client(enforce_csrf_checks=True)
    protected.force_login(customer)
    assert protected.get(url).status_code == 200
    assert protected.post(url, {}).status_code == 403


def test_missing_email_and_ownership_isolation(
    client, customer, staff_user, mailoutbox
):
    client.force_login(customer)
    response = client.get(reverse("accounts:security"))
    assert reverse("accounts:password_change") in response.content.decode()
    response = client.post(
        reverse("accounts:password_change"),
        {
            "old_password": "customer123",
            "new_password1": NEW_PASSWORD,
            "new_password2": NEW_PASSWORD,
            "user": staff_user.pk,
        },
    )
    assert response.status_code == 302
    staff_user.refresh_from_db()
    assert staff_user.check_password("employee123")
    customer.refresh_from_db()
    assert customer.check_password(NEW_PASSWORD)
    assert not mailoutbox
