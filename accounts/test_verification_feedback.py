"""Phase 3 feedback, precise limits, link edge cases, and failure recovery."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

import pytest
from django.core import signing
from django.db import close_old_connections
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import SecurityRequest, SecurityRequestLock, User
from accounts.verification import SALT, verification_token, verify_email_link

pytestmark = pytest.mark.django_db


def assign_email(user):
    user.email = "owner@example.com"
    user.save()
    return user


@pytest.mark.parametrize("kind", ["account", "destination"])
@pytest.mark.parametrize("elapsed,allowed,wait", [(59, False, 1), (60, True, 0)])
def test_exact_cooldown_feedback(customer, kind, elapsed, allowed, wait):
    assign_email(customer)
    now = timezone.now()
    SecurityRequest.objects.create(
        kind=kind,
        key=str(customer.pk) if kind == "account" else customer.email,
        created_at=now,
    )
    with patch(
        "accounts.models.timezone.now", return_value=now + timedelta(seconds=elapsed)
    ):
        result = SecurityRequest.objects.reserve_result("network", user=customer)
    assert bool(result) == allowed
    assert result.retry_after == wait
    if not allowed:
        assert result.reason == f"{kind}_cooldown"
        assert "1 second before retrying" in result.message
        assert "Verify email" in result.message


@pytest.mark.parametrize("kind", ["account", "destination"])
@pytest.mark.parametrize("elapsed,allowed", [(3599, False), (3600, True)])
def test_exact_hourly_feedback(customer, kind, elapsed, allowed):
    assign_email(customer)
    now = timezone.now()
    for offset in range(5):
        SecurityRequest.objects.create(
            kind=kind,
            key=str(customer.pk) if kind == "account" else customer.email,
            created_at=now + timedelta(seconds=offset * 60),
        )
    with patch(
        "accounts.models.timezone.now", return_value=now + timedelta(seconds=elapsed)
    ):
        result = SecurityRequest.objects.reserve_result("network", user=customer)
    assert bool(result) == allowed
    if not allowed:
        assert result.reason == f"{kind}_hour"
        assert result.retry_after == 1
        assert "five-per-hour" in result.message


def test_longest_applicable_wait_is_reported(customer):
    assign_email(customer)
    now = timezone.now()
    for offset in range(5):
        SecurityRequest.objects.create(
            kind="destination",
            key=customer.email,
            created_at=now - timedelta(seconds=300 - offset * 60),
        )
    SecurityRequest.objects.create(kind="account", key=str(customer.pk), created_at=now)
    with patch("accounts.models.timezone.now", return_value=now):
        result = SecurityRequest.objects.reserve_result("network", user=customer)
    assert result.reason == "destination_hour"
    assert result.retry_after == 3300


def test_network_boundary_counts_suppression_and_does_not_record_sends(
    customer, settings
):
    settings.SECURITY_EMAIL_NETWORK_LIMIT = 2
    now = timezone.now()
    for offset in [0, 10]:
        SecurityRequest.objects.create(
            kind="network", key="network", created_at=now + timedelta(seconds=offset)
        )
    assign_email(customer)
    with patch(
        "accounts.models.timezone.now", return_value=now + timedelta(seconds=3599)
    ):
        result = SecurityRequest.objects.reserve_result("network", user=customer)
    assert result.reason == "network"
    assert result.retry_after == 11  # The suppressed request is counted too.
    assert "network email request limits" in result.message
    assert SecurityRequest.objects.filter(kind="network").count() == 3
    assert not SecurityRequest.objects.filter(kind="account").exists()
    with patch(
        "accounts.models.timezone.now", return_value=now + timedelta(seconds=3610)
    ):
        assert SecurityRequest.objects.reserve_result("network", user=customer)


@pytest.mark.parametrize(
    "state,message",
    [
        ("verified", "already verified"),
        ("missing", "Add or correct"),
        ("invalid", "Add or correct"),
    ],
)
def test_ineligible_requests_count_network_without_misleading_wait(
    client, customer, mailoutbox, state, message
):
    if state == "verified":
        assign_email(customer)
        customer.email_verified = True
        customer.save()
    elif state == "invalid":
        customer.email = "invalid"
        customer.save()
    client.force_login(customer)
    response = client.post(reverse("accounts:verification_request"), follow=True)
    assert message in response.content.decode()
    assert SecurityRequest.objects.filter(kind="network").count() == 1
    assert not SecurityRequest.objects.filter(kind="account").exists()
    assert not mailoutbox


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        "text",
        {},
        {"user": "1", "email": "owner@example.com"},
        {"user": True, "email": "owner@example.com"},
        {"user": 2**100, "email": "owner@example.com"},
        {"user": 1, "email": []},
        {"user": 1, "email": "owner@example.com", "revision": -1},
        {"user": 1, "email": "owner@example.com", "revision": "0"},
    ],
)
def test_malformed_signed_payload_is_safe(client, data):
    token = signing.dumps(data, salt=SALT)
    response = client.get(reverse("accounts:verify_email", args=[token]))
    assert response.status_code == 200
    assert response.context["verification_status"] == "invalid"
    assert "Copy the complete link" in response.content.decode()
    assert not response.context["user"].is_authenticated


@pytest.mark.parametrize("age,status", [(86400, "verified"), (86401, "expired")])
def test_exact_link_expiry(client, customer, age, status):
    assign_email(customer)
    with patch("django.core.signing.time.time", return_value=100000):
        token = verification_token(customer)
    with patch("django.core.signing.time.time", return_value=100000 + age):
        response = client.get(reverse("accounts:verify_email", args=[token]))
    assert response.context["verification_status"] == status
    customer.refresh_from_db()
    assert customer.email_verified == (status == "verified")
    if status == "expired":
        assert "expired after 24 hours" in response.content.decode()
        assert reverse("accounts:verification_request") in response.content.decode()


def test_superseded_link_does_not_touch_signed_in_account(client, customer, staff_user):
    assign_email(customer)
    token = verification_token(customer)
    customer.correct_unverified_email("new@example.com")
    client.force_login(staff_user)
    response = client.get(reverse("accounts:verify_email", args=[token]))
    assert response.context["verification_status"] == "superseded"
    assert "verify your current address" in response.content.decode()
    customer.refresh_from_db()
    staff_user.refresh_from_db()
    assert not customer.email_verified and not staff_user.email_verified
    assert customer.email == "new@example.com"


def test_repeated_and_earlier_resend_links_are_harmless(
    client, customer, staff_user, mailoutbox
):
    assign_email(customer)
    now = timezone.now()
    client.force_login(customer)
    with (
        patch("accounts.models.timezone.now", return_value=now),
        patch("django.core.signing.time.time", return_value=100000),
    ):
        client.post(reverse("accounts:verification_request"))
    with (
        patch("accounts.models.timezone.now", return_value=now + timedelta(seconds=60)),
        patch("django.core.signing.time.time", return_value=100060),
    ):
        client.post(reverse("accounts:verification_request"))
    assert len(mailoutbox) == 2
    tokens = [
        message.body.split("/accounts/verify/")[1].split("/")[0]
        for message in mailoutbox
    ]
    assert tokens[0] != tokens[1]
    client.force_login(staff_user)
    with patch("django.core.signing.time.time", return_value=100061):
        first = client.get(reverse("accounts:verify_email", args=[tokens[0]]))
        second = client.get(reverse("accounts:verify_email", args=[tokens[1]]))
        repeated = client.get(reverse("accounts:verify_email", args=[tokens[0]]))
    assert first.context["verification_status"] == "verified"
    for response in [second, repeated]:
        assert response.context["verification_status"] == "already_verified"
        assert "Sign in to your account" in response.content.decode()
        assert response.context["user"].pk == staff_user.pk
    staff_user.refresh_from_db()
    assert not staff_user.email_verified


@pytest.mark.parametrize("zero_delivery", [False, True])
def test_failed_delivery_and_repeated_retries_preserve_state(
    client, customer, mailoutbox, zero_delivery
):
    assign_email(customer)
    original_token = verification_token(customer)
    now = timezone.now()
    client.force_login(customer)
    kwargs = (
        {"return_value": 0} if zero_delivery else {"side_effect": OSError("offline")}
    )
    with (
        patch("accounts.models.timezone.now", return_value=now),
        patch("accounts.verification.send_mail", **kwargs),
    ):
        response = client.post(reverse("accounts:verification_request"), follow=True)
    assert "Email delivery failed" in response.content.decode()
    for offset in [1, 2, 59]:
        with patch(
            "accounts.models.timezone.now", return_value=now + timedelta(seconds=offset)
        ):
            response = client.post(
                reverse("accounts:verification_request"), follow=True
            )
        assert "Please wait" in response.content.decode()
    assert not mailoutbox
    assert SecurityRequest.objects.filter(kind="account").count() == 1
    with patch(
        "accounts.models.timezone.now", return_value=now + timedelta(seconds=60)
    ):
        response = client.post(reverse("accounts:verification_request"), follow=True)
    assert "Verification email sent" in response.content.decode()
    customer.refresh_from_db()
    assert customer.email == "owner@example.com" and not customer.email_verified
    assert customer.email_revision == 0
    assert len(mailoutbox) == 1
    assert verify_email_link(original_token).status == "verified"


def test_stale_user_cannot_send_for_corrected_or_verified_address(customer):
    assign_email(customer)
    stale = User.objects.get(pk=customer.pk)
    customer.correct_unverified_email("new@example.com")
    result = SecurityRequest.objects.reserve_result("network", user=stale)
    assert result.allowed
    assert stale.email == "new@example.com"
    assert SecurityRequest.objects.filter(
        kind="destination", key="new@example.com"
    ).exists()
    verify_email_link(verification_token(customer))
    assert (
        SecurityRequest.objects.reserve_result("other-network", user=stale).reason
        == "verified"
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind", ["account", "destination", "network"])
def test_concurrent_requests_cannot_bypass_hourly_or_network_limits(kind, settings):
    settings.SECURITY_EMAIL_NETWORK_LIMIT = 1 if kind == "network" else 30
    user = User.objects.create_user(username="concurrent", email="owner@example.com")
    SecurityRequestLock.objects.get_or_create(pk=1)
    now = timezone.now()
    if kind != "network":
        for offset in range(4):
            SecurityRequest.objects.create(
                kind=kind,
                key=str(user.pk) if kind == "account" else user.email,
                created_at=now - timedelta(seconds=300 - offset * 60),
            )
    barrier = Barrier(2)

    def attempt(_):
        close_old_connections()
        try:
            account = User.objects.get(pk=user.pk)
            barrier.wait()
            return bool(SecurityRequest.objects.reserve_result("network", user=account))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, range(2)))
    assert sorted(outcomes) == [False, True]
    assert SecurityRequest.objects.filter(kind="network").count() == 2


@pytest.mark.django_db(transaction=True)
def test_simultaneous_link_visits_verify_once():
    user = User.objects.create_user(username="concurrent", email="owner@example.com")
    token = verification_token(user)
    SecurityRequestLock.objects.get_or_create(pk=1)
    barrier = Barrier(2)

    def visit(_):
        close_old_connections()
        try:
            barrier.wait()
            response = Client().get(reverse("accounts:verify_email", args=[token]))
            assert response.status_code == 200
            # Template-render signals collect contexts globally across threads;
            # assert each response's own rendered body instead.
            body = response.content.decode()
            if "already verified" in body:
                return "already_verified"
            assert "Email verified." in body
            return "verified"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(visit, range(2)))
    assert sorted(outcomes) == ["already_verified", "verified"]
    user.refresh_from_db()
    assert user.email_verified
