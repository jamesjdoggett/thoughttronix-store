import re

import pytest
from django.urls import reverse

from orders.models import Cart
from orders.test_checkout_form import VALID_DATA

from .models import Wishlist


@pytest.mark.parametrize("htmx", [False, True])
def test_cart_feedback_and_wired_form(client, customer, product, htmx):
    Wishlist.for_user(customer).add(product)
    client.force_login(customer)
    destination = reverse("wishlist:detail")
    action = reverse("wishlist:add_to_cart", args=[product.pk])
    page = client.get(destination).content.decode()
    form = next(
        form
        for form in re.findall(r"<form\b.*?</form>", page, re.S)
        if f'action="{action}"' in form
    )
    assert f'hx-post="{action}"' in form
    assert f'hx-target="#wishlist-cart-{product.pk}" hx-swap="outerHTML"' in form
    assert 'name="csrfmiddlewaretoken"' in form
    response = client.post(
        action,
        {"next": destination},
        HTTP_HX_REQUEST="true" if htmx else "false",
        follow=not htmx,
    )
    html = response.content.decode()
    assert "added to cart. Quantity: 1." in html
    assert "In cart: 1" in html
    assert response.context["cart_item_count"] == 1
    assert response.context["wishlist_item_count"] == 1
    if htmx:
        assert "<html" not in html.lower()
        assert 'role="status"' in html
        assert re.search(
            r'<a\b(?=[^>]*id="cart-badge")(?=[^>]*hx-swap-oob="true")', html
        )
        assert f'name="next" value="{destination}"' in html
    else:
        assert response.redirect_chain == [(destination, 302)]


@pytest.mark.parametrize("htmx", [False, True])
def test_cart_rechecks_availability_and_preserves_removal(
    client, customer, product, htmx
):
    entry = Wishlist.for_user(customer).add(product)
    client.force_login(customer)
    destination = reverse("wishlist:detail")
    assert b"Add to cart" in client.get(destination).content
    product.is_available = False
    product.save(update_fields=["is_available"])
    response = client.post(
        reverse("wishlist:add_to_cart", args=[product.pk]),
        {"next": destination},
        HTTP_HX_REQUEST="true" if htmx else "false",
        follow=not htmx,
    )
    assert b"no longer available" in response.content
    assert b"Unavailable" in response.content
    assert b"Add to cart" not in response.content
    assert not Cart.objects.exists()
    entry.refresh_from_db()
    page = client.get(destination)
    assert b"Add to cart" not in page.content
    assert b"Unavailable" in page.content
    assert reverse("wishlist:remove", args=[product.pk]).encode() in page.content
    client.post(reverse("wishlist:remove", args=[product.pk]))
    assert not Wishlist.for_user(customer).entries.exists()


@pytest.mark.parametrize("htmx", [False, True])
def test_cart_action_is_owner_scoped(client, customer, staff_user, product, htmx):
    wishlist = Wishlist.for_user(customer)
    wishlist.add(product)
    action = reverse("wishlist:add_to_cart", args=[product.pk])
    client.force_login(staff_user)
    data = {"owner": customer.pk, "wishlist": wishlist.pk, "user": customer.pk}
    headers = {"HX-Request": "true"} if htmx else {}
    assert client.post(action, data, headers=headers).status_code == 404
    assert not Cart.objects.exists()
    Wishlist.for_user(staff_user).add(product)
    client.post(action, data, headers=headers)
    assert Cart.objects.get().user == staff_user
    assert wishlist.entries.count() == 1


@pytest.mark.parametrize(
    "destination", ["https://evil.test/", "//evil.test/", "/\\evil.test/"]
)
def test_cart_rejects_external_return(client, customer, product, destination):
    Wishlist.for_user(customer).add(product)
    client.force_login(customer)
    response = client.post(
        reverse("wishlist:add_to_cart", args=[product.pk]), {"next": destination}
    )
    assert response.url == reverse("wishlist:detail")


def test_purchase_preserves_saved_interest_and_requires_verification(
    client, customer, product
):
    entry = Wishlist.for_user(customer).add(product)
    client.force_login(customer)
    client.post(reverse("wishlist:add_to_cart", args=[product.pk]))
    response = client.post(reverse("orders:checkout"), VALID_DATA)
    assert response.url.startswith(reverse("accounts:security"))
    assert not customer.orders.exists()
    assert Cart.for_user(customer).items.count() == 1
    customer.email = "customer@example.com"
    customer.email_verified = True
    customer.save()
    preview = client.get(reverse("orders:checkout"))
    response = client.post(
        reverse("orders:checkout"),
        {**VALID_DATA, "pricing_snapshot": preview.context["pricing_snapshot"]},
    )
    assert response.status_code == 302
    assert customer.orders.count() == 1
    assert not Cart.for_user(customer).items.exists()
    entry.refresh_from_db()
    assert client.get(reverse("wishlist:detail")).context["wishlist_item_count"] == 1
