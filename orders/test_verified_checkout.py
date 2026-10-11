"""Phase 4 purchase eligibility and safe verification continuation."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from accounts.verification import verification_token
from orders.models import Cart, Order
from orders.services import place_order
from orders.test_checkout_form import VALID_DATA


@pytest.mark.parametrize(
    "role", [{}, {"is_staff": True}, {"is_staff": True, "is_superuser": True}]
)
@pytest.mark.parametrize("htmx", [False, True])
def test_unverified_checkout_preserves_cart(client, product, role, htmx):
    user = get_user_model().objects.create_user(
        username="buyer", password="pass", **role
    )
    cart = Cart.for_user(user)
    cart.add(product)
    cart.coupon_code = "SAVED"
    cart.save()
    Order.objects.create(user=user, email="historic@example.com", total="1.00")
    client.force_login(user)
    destination = reverse("accounts:security") + "?next=" + reverse("orders:checkout")
    for method in [client.get, client.post]:
        response = method(
            reverse("orders:checkout"), HTTP_HX_REQUEST="true" if htmx else "false"
        )
        if htmx:
            assert response.headers["HX-Redirect"] == destination
        else:
            assert response.url == destination
    with pytest.raises(ValueError, match="Verify your email"):
        place_order(cart, user, VALID_DATA)
    cart.refresh_from_db()
    assert cart.items.get().quantity == 1
    assert cart.coupon_code == "SAVED"
    assert Order.objects.get().email == "historic@example.com"
    for route in ["products:catalog", "orders:cart", "orders:history"]:
        assert client.get(reverse(route)).status_code == 200
    assert (
        client.post(
            reverse("orders:increment", args=[cart.items.get().pk]),
            HTTP_HX_REQUEST="true",
        ).status_code
        == 200
    )
    assert (
        client.post(
            reverse("orders:decrement", args=[cart.items.get().pk]),
            HTTP_HX_REQUEST="true",
        ).status_code
        == 200
    )
    client.logout()
    assert client.login(username="buyer", password="pass")
    response = client.get(destination)
    assert b"Add or correct email" in response.content
    assert b"?next=/checkout/" in response.content


def test_service_checks_database_and_zero_total(customer, cart, cart_item):
    cart_item.product.price = 0
    cart_item.product.save()
    get_user_model().objects.filter(pk=customer.pk).update(email_verified=False)
    assert customer.email_verified  # stale authenticated instance
    with pytest.raises(ValueError, match="Verify your email"):
        place_order(cart, customer, VALID_DATA)
    assert cart.items.exists()
    assert not Order.objects.exists()


def test_matching_verification_continues_checkout(client, customer, cart_item):
    customer.email_verified = False
    customer.save()
    client.force_login(customer)
    response = client.get(
        reverse("accounts:verify_email", args=[verification_token(customer)])
    )
    assert b"Continue to checkout" in response.content
    preview = client.get(reverse("orders:checkout"))
    response = client.post(
        reverse("orders:checkout"),
        {**VALID_DATA, "pricing_snapshot": preview.context["pricing_snapshot"]},
    )
    assert response.status_code == 302
    assert Order.objects.count() == 1


@pytest.mark.parametrize("different_account", [False, True])
def test_verification_does_not_authenticate_visitor(
    client, customer, different_account
):
    if different_account:
        other = get_user_model().objects.create_user(username="other")
        client.force_login(other)
    response = client.get(
        reverse("accounts:verify_email", args=[verification_token(customer)])
    )
    assert b"Sign in to your account" in response.content
    assert b"Continue to checkout" not in response.content
    assert client.session.get("_auth_user_id") == (
        str(other.pk) if different_account else None
    )


@pytest.mark.parametrize(
    "next_url", ["https://example.com", "//example.com", "/orders/cart/"]
)
def test_security_ignores_other_continuations(client, customer, next_url):
    client.force_login(customer)
    response = client.get(reverse("accounts:security"), {"next": next_url})
    assert not response.context["checkout_next"]
    assert b"Continue to checkout" not in response.content


def test_checkout_continuation_survives_correction_and_resend(
    client, customer, mailoutbox
):
    customer.email_verified = False
    customer.save()
    client.force_login(customer)
    suffix = "?next=" + reverse("orders:checkout")
    response = client.post(
        reverse("accounts:email_correction") + suffix,
        {"email": "corrected@example.com", "current_password": "customer123"},
    )
    assert response.url == reverse("accounts:security") + suffix
    response = client.get(response.url)
    assert (
        reverse("accounts:verification_request") + suffix
    ).encode() in response.content
    response = client.post(reverse("accounts:verification_request") + suffix)
    assert response.url == reverse("accounts:verification_request") + suffix
    response = client.post(
        reverse("accounts:verification_request") + "?next=https://example.com"
    )
    assert response.url == reverse("accounts:verification_request")
