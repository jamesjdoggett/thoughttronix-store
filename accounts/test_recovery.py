"""Recovery privacy, password policy, security events, and atomic consumption."""

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from django.db import close_old_connections
from django.test import Client, RequestFactory
from django.urls import reverse
from django.utils import timezone

from accounts.models import SecurityRequest, User
from accounts.recovery import (
    recovery_token,
    recovery_token_generator,
    recovery_user,
    reset_password,
    send_recovery,
)
from accounts.verification import verification_token, verify_email_link

pytestmark = pytest.mark.django_db
PASSWORD = "Orbit!Lantern72Quartz"


@pytest.fixture
def eligible(customer):
    customer.email = "owner@example.com"
    customer.email_verified = True
    customer.save()
    return customer


def public_content(response):
    content = re.sub(rb'(X-CSRFToken": ")[^"]+', rb"\1TOKEN", response.content)
    return re.sub(rb'(name="csrfmiddlewaretoken" value=")[^"]+', rb"\1TOKEN", content)


def request_reset(client, email="owner@example.com"):
    return client.post(
        reverse("accounts:password_reset"), {"email": email}, follow=True
    )


def submit(client, token, password=PASSWORD, confirmation=None):
    url = reverse("accounts:password_reset_confirm", args=token.split("~", 1))
    page = client.get(url, follow=True)
    target = page.request["PATH_INFO"]
    return client.post(
        target,
        {
            "new_password1": password,
            "new_password2": password if confirmation is None else confirmation,
        },
    )


@pytest.mark.parametrize(
    "address",
    ["unknown@example.com", "", "invalid", "pending@example.com", "owner@example.com"],
)
def test_generic_ineligible_requests(client, customer, mailoutbox, address):
    customer.email = "owner@example.com"
    customer.pending_email = "pending@example.com"
    customer.save()
    expected = public_content(client.get(reverse("accounts:password_reset_done")))
    response = request_reset(client, address)
    assert public_content(response) == expected
    assert not mailoutbox
    assert SecurityRequest.objects.filter(kind="network").count() == 1


@pytest.mark.parametrize(
    "staff,superuser", [(False, False), (True, False), (True, True)]
)
def test_reset_revokes_sessions_cancels_pending_and_alerts(
    client, eligible, mailoutbox, staff, superuser
):
    eligible.is_staff, eligible.is_superuser = staff, superuser
    eligible.pending_email = "pending@example.com"
    eligible.save()
    pending = verification_token(eligible)
    other = Client()
    for browser in (client, other):
        browser.force_login(eligible)
    token, sibling = recovery_token(eligible), recovery_token(eligible)
    assert submit(client, token).url == reverse("accounts:login")
    eligible.refresh_from_db()
    assert eligible.check_password(PASSWORD)
    assert eligible.pending_email == ""
    assert recovery_user(sibling) is None
    assert verify_email_link(pending).user is None
    assert submit(other, token).status_code == 200
    for browser in (client, other):
        assert browser.get(reverse("accounts:security")).status_code == 302
    assert not Client().login(username=eligible.username, password="customer123")
    assert Client().login(username=eligible.username, password=PASSWORD)
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == [eligible.email]
    for secret in (PASSWORD, token, "http"):
        assert secret not in mailoutbox[0].body


@pytest.mark.parametrize("seconds,valid", [(86400, True), (86401, False)])
def test_expiry_boundary(eligible, seconds, valid):
    with patch.object(
        recovery_token_generator, "_now", return_value=datetime(2033, 5, 18)
    ):
        token = recovery_token(eligible)
    with patch.object(
        recovery_token_generator,
        "_now",
        return_value=datetime(2033, 5, 18) + timedelta(seconds=seconds),
    ):
        assert bool(recovery_user(token)) == valid


@pytest.mark.parametrize(
    "password,confirmation",
    [
        ("aB!4", None),
        ("password", None),
        ("9375612048", None),
        ("customer", None),
        (PASSWORD, "different"),
    ],
)
def test_password_validation(client, eligible, mailoutbox, password, confirmation):
    token = recovery_token(eligible)
    response = submit(client, token, password, confirmation)
    assert response.context["form"].errors
    eligible.refresh_from_db()
    assert eligible.check_password("customer123")
    assert recovery_user(token)
    assert not mailoutbox


def test_normalized_delivery_and_shared_cooldown(client, eligible, mailoutbox):
    request_reset(client, " OWNER@EXAMPLE.COM ")
    assert len(mailoutbox) == 1
    token = "~".join(mailoutbox[0].body.split("/password/reset/")[1].split("/")[:2])
    assert recovery_user(token)
    expected = public_content(client.get(reverse("accounts:password_reset_done")))
    assert public_content(request_reset(client)) == expected
    assert len(mailoutbox) == 1
    SecurityRequest.objects.exclude(kind="network").update(
        created_at=timezone.now() - timedelta(seconds=60)
    )
    request_reset(client)
    assert len(mailoutbox) == 2
    assert recovery_user(token)
    client.force_login(eligible)
    eligible.pending_email = "pending@example.com"
    eligible.save()
    client.post(reverse("accounts:verification_request"))
    assert len(mailoutbox) == 2


@pytest.mark.parametrize("kind", ["account", "destination", "network"])
def test_hourly_limits_generic(client, eligible, mailoutbox, kind, settings):
    key = {
        "account": str(eligible.pk),
        "destination": eligible.email,
        "network": "127.0.0.1",
    }[kind]
    count = settings.SECURITY_EMAIL_NETWORK_LIMIT if kind == "network" else 5
    SecurityRequest.objects.bulk_create(
        [
            SecurityRequest(
                kind=kind, key=key, created_at=timezone.now() - timedelta(minutes=10)
            )
            for _ in range(count)
        ]
    )
    expected = public_content(client.get(reverse("accounts:password_reset_done")))
    assert public_content(request_reset(client)) == expected
    assert not mailoutbox


@pytest.mark.parametrize("result", [OSError("offline"), 0])
def test_delivery_failures_generic_and_reset_still_succeeds(client, eligible, result):
    kwargs = (
        {"side_effect": result}
        if isinstance(result, Exception)
        else {"return_value": result}
    )
    expected = public_content(client.get(reverse("accounts:password_reset_done")))
    with patch("accounts.recovery.send_mail", **kwargs):
        assert public_content(request_reset(client)) == expected
    with patch("accounts.passwords.send_mail", **kwargs):
        assert submit(client, recovery_token(eligible)).status_code == 302
    eligible.refresh_from_db()
    assert eligible.check_password(PASSWORD)


def test_password_and_email_events_invalidate_issued_links(
    client, eligible, mailoutbox
):
    request_reset(client)
    token = recovery_token(eligible)
    client.force_login(eligible)
    client.post(
        reverse("accounts:password_change"),
        {
            "old_password": "customer123",
            "new_password1": PASSWORD,
            "new_password2": PASSWORD,
        },
    )
    assert recovery_user(token) is None
    eligible.refresh_from_db()
    token = recovery_token(eligible)
    eligible.stage_email_replacement("replacement@example.com")
    assert recovery_user(token)
    assert verify_email_link(verification_token(eligible)).user
    assert recovery_user(token) is None
    mailoutbox.clear()
    SecurityRequest.objects.all().delete()
    request_reset(client, "owner@example.com")
    assert not mailoutbox
    request_reset(client, "replacement@example.com")
    assert mailoutbox[0].to == ["replacement@example.com"]


def test_invalid_links_and_csrf(client, eligible):
    assert recovery_user("malformed") is None
    response = client.get(
        reverse("accounts:password_reset_confirm", args=["invalid", "invalid"])
    )
    assert reverse("accounts:password_reset") in response.content.decode()
    protected = Client(enforce_csrf_checks=True)
    assert (
        protected.post(
            reverse("accounts:password_reset"), {"email": eligible.email}
        ).status_code
        == 403
    )
    assert submit(protected, recovery_token(eligible)).status_code == 403


@pytest.mark.django_db(transaction=True)
def test_simultaneous_consumption():
    user = User.objects.create_user(
        username="race",
        password="Old!Quartz72",
        email="race@example.com",
        email_verified=True,
    )
    token = recovery_token(user)

    def consume(_):
        close_old_connections()
        try:
            account = recovery_user(token)
            return reset_password(account, PASSWORD) if account else False
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(consume, range(2))) == 1


def test_full_signup_verification_checkout_and_recovery(client, product, mailoutbox):
    client.post(
        reverse("accounts:signup"),
        {
            "username": "journey",
            "email": "journey@example.com",
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
    )
    user = User.objects.get(username="journey")
    assert client.login(username=user.username, password=PASSWORD)
    assert client.get(reverse("orders:checkout")).status_code == 302
    assert verify_email_link(verification_token(user)).user
    user.refresh_from_db()
    from orders.models import Cart

    Cart.for_user(user).add(product)
    assert client.get(reverse("orders:checkout")).status_code == 200
    SecurityRequest.objects.all().delete()
    send_recovery(RequestFactory().post("/"), user.email)
    token = "~".join(mailoutbox[-1].body.split("/password/reset/")[1].split("/")[:2])
    assert submit(client, token, "New!Lantern83Quartz").status_code == 302
    assert client.get(reverse("accounts:security")).status_code == 302
    assert client.login(username=user.username, password="New!Lantern83Quartz")
    assert client.get(reverse("orders:checkout")).status_code == 200


@pytest.mark.parametrize(
    "email,active", [("", True), ("invalid", True), ("owner@example.com", False)]
)
def test_invalid_or_inactive_verified_accounts(
    client, eligible, mailoutbox, email, active
):
    eligible.email, eligible.is_active = email, active
    eligible.save()
    request_reset(client, email)
    assert not mailoutbox
    assert recovery_user(recovery_token(eligible)) is None


def test_second_distinct_link_and_signin_preserve_first(client, eligible, mailoutbox):
    with patch.object(
        recovery_token_generator, "_now", return_value=datetime(2033, 5, 18)
    ):
        first = recovery_token(eligible)
    with patch.object(
        recovery_token_generator,
        "_now",
        return_value=datetime(2033, 5, 18) + timedelta(seconds=60),
    ):
        second = recovery_token(eligible)
        assert first != second
        assert client.login(username=eligible.username, password="customer123")
        assert recovery_user(first)
        assert recovery_user(second)
        assert submit(client, first).status_code == 302
        assert recovery_user(second) is None


@pytest.mark.django_db(transaction=True)
def test_concurrent_recovery_requests_share_send_reservation(mailoutbox):
    user = User.objects.create_user(
        username="sends",
        password=PASSWORD,
        email="sends@example.com",
        email_verified=True,
    )

    def request(_):
        close_old_connections()
        try:
            send_recovery(RequestFactory().post("/"), user.email)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(request, range(2)))
    assert len(mailoutbox) == 1
    assert SecurityRequest.objects.filter(kind="network").count() == 2


def test_django_hides_reset_token_and_binds_it_to_browser(client, eligible):
    token = recovery_token(eligible)
    url = reverse("accounts:password_reset_confirm", args=token.split("~", 1))
    response = client.get(url)
    assert response.status_code == 302
    assert token.split("~", 1)[1] not in response.url
    assert response.url.endswith("/set-password/")
    assert "no-store" in response.headers["Cache-Control"]
    assert Client().get(response.url).context["validlink"] is False
    assert client.get(response.url).context["validlink"] is True
    assert not client.get(reverse("accounts:security")).status_code == 200


def test_reset_token_cannot_target_another_account(client, eligible, staff_user):
    staff_user.email = "staff@example.com"
    staff_user.email_verified = True
    staff_user.save()
    uid = recovery_token(staff_user).split("~", 1)[0]
    secret = recovery_token(eligible).split("~", 1)[1]
    response = client.get(
        reverse("accounts:password_reset_confirm", args=[uid, secret])
    )
    assert response.context["validlink"] is False


def test_unusable_password_is_not_recoverable(client, eligible, mailoutbox):
    eligible.set_unusable_password()
    eligible.save()
    response = request_reset(client)
    assert b"If an eligible account matches" in response.content
    assert not mailoutbox
    assert recovery_user(recovery_token(eligible)) is None


def test_reset_runs_django_password_changed_hook(client, eligible):
    with patch("django.contrib.auth.password_validation.password_changed") as changed:
        assert submit(client, recovery_token(eligible)).status_code == 302
    changed.assert_called_once()
    assert changed.call_args.args[0] == PASSWORD
    assert changed.call_args.args[1].pk == eligible.pk


def test_legacy_and_malformed_link_give_retry_guidance(client):
    response = client.get(
        reverse("accounts:password_reset_legacy", args=["old-signed-token"])
    )
    assert reverse("accounts:password_reset") in response.content.decode()
    response = request_reset(client, "invalid\x00@example.com")
    assert b"If an eligible account matches" in response.content
    assert SecurityRequest.objects.filter(kind="network").count() == 1
