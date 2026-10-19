import re

import pytest
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from .models import Wishlist


def test_sharing_lifecycle(client, customer, product):
    wishlist = Wishlist.for_user(customer)
    wishlist.add(product)
    assert wishlist.share_token is None
    client.force_login(customer)
    response = client.post(reverse("wishlist:enable_sharing"))
    assert response.status_code == 302
    wishlist.refresh_from_db()
    original_token = wishlist.share_token
    assert original_token
    original_url = reverse("wishlist:shared", args=[original_token])
    client.logout()
    assert client.get(original_url).status_code == 200
    client.force_login(customer)
    client.post(reverse("wishlist:disable_sharing"))
    wishlist.refresh_from_db()
    assert wishlist.share_token is None
    assert client.get(original_url).status_code == 404
    client.post(reverse("wishlist:enable_sharing"))
    wishlist.refresh_from_db()
    assert wishlist.share_token and wishlist.share_token != original_token
    assert client.get(original_url).status_code == 404
    client.logout()
    assert (
        client.get(reverse("wishlist:shared", args=[wishlist.share_token])).status_code
        == 200
    )


def test_shared_page_privacy_and_live_products(
    client, customer, staff_user, product, unavailable_product
):
    customer.email = "wishlist-owner@example.com"
    customer.save()
    wishlist = Wishlist.for_user(customer)
    wishlist.add(product)
    unavailable_product.is_available = True
    unavailable_product.save()
    wishlist.add(unavailable_product)
    unavailable_product.is_available = False
    unavailable_product.save()
    wishlist.enable_sharing()
    product.name = "Current product name"
    product.price = "123.45"
    product.save()
    url = reverse("wishlist:shared", args=[wishlist.share_token])

    for viewer in (None, staff_user, customer):
        if viewer:
            client.force_login(viewer)
        else:
            client.logout()
        response = client.get(url)
        assert response.status_code == 200
        html = response.content.decode()
        assert "Shared wishlist" in html
        assert "Current product name" in html
        assert "$123.45" in html
        assert f'href="{product.get_absolute_url()}"' in html
        assert unavailable_product.name in html
        assert unavailable_product.catalog_image_url in html
        assert "$139.00" in html
        assert "Unavailable" in html
        assert unavailable_product.get_absolute_url() not in html
        assert reverse("wishlist:remove", args=[product.pk]) not in html
        assert reverse("wishlist:add_to_cart", args=[product.pk]) not in html
        assert reverse("wishlist:save", args=[product.pk]) not in html
        assert "Enable sharing" not in html
        assert "Disable sharing" not in html
        assert customer.email not in html
        if viewer != customer:
            assert customer.username not in html
        if viewer:
            assert f"Hi, {viewer.username}" in html


pytestmark = pytest.mark.django_db


def test_owner_controls_and_idempotent_enable(client, customer):
    client.force_login(customer)
    detail = reverse("wishlist:detail")
    page = client.get(detail)
    assert b"Enable sharing" in page.content
    assert not Wishlist.objects.exists()
    response = client.post(reverse("wishlist:enable_sharing"), follow=True)
    wishlist = customer.wishlist
    token = wishlist.share_token
    url = "http://testserver" + reverse("wishlist:shared", args=[token])
    html = response.content.decode()
    assert f'readonly value="{url}"' in html
    assert "Open shared page" in html
    assert "Disable sharing" in html
    assert 'name="csrfmiddlewaretoken"' in html
    assert len(token) >= 43
    client.post(reverse("wishlist:enable_sharing"))
    wishlist.refresh_from_db()
    assert wishlist.share_token == token
    client.post(reverse("wishlist:disable_sharing"))
    assert b"Enable sharing" in client.get(detail).content


@pytest.mark.parametrize("action", ["enable_sharing", "disable_sharing"])
def test_sharing_post_csrf_and_owner_isolation(client, customer, staff_user, action):
    owner = Wishlist.for_user(customer)
    owner.enable_sharing()
    token = owner.share_token
    url = reverse(f"wishlist:{action}")
    client.force_login(staff_user)
    assert client.get(url).status_code == 405
    secure_client = Client(enforce_csrf_checks=True)
    secure_client.force_login(staff_user)
    assert secure_client.post(url).status_code == 403
    page = secure_client.get(reverse("wishlist:detail"))
    csrf = secure_client.cookies["csrftoken"].value
    assert page.status_code == 200
    assert secure_client.post(url, {"csrfmiddlewaretoken": csrf}).status_code == 302
    response = client.post(
        url, {"owner": customer.pk, "wishlist": owner.pk, "token": token}
    )
    assert response.status_code == 302
    owner.refresh_from_db()
    assert owner.share_token == token
    if action == "enable_sharing":
        assert staff_user.wishlist.share_token != token
    client.logout()
    response = client.post(url, {"token": token})
    assert response.status_code == 302
    assert response.url.startswith(reverse("accounts:login"))
    response = client.post(url, {"token": token}, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    assert response["HX-Redirect"].startswith(reverse("accounts:login"))
    owner.refresh_from_db()
    assert owner.share_token == token


def test_sharing_tokens_are_unique(customer, staff_user):
    first = Wishlist.for_user(customer)
    second = Wishlist.for_user(staff_user)
    assert first.share_token is second.share_token is None
    first.enable_sharing()
    second.enable_sharing()
    assert first.share_token != second.share_token
    with transaction.atomic(), pytest.raises(IntegrityError):
        Wishlist.objects.filter(pk=second.pk).update(share_token=first.share_token)


def test_shared_pagination_and_current_membership(client, paginated_wishlist):
    wishlist = paginated_wishlist
    wishlist.enable_sharing()
    wishlist.entries.update(saved_at=timezone.now())
    url = reverse("wishlist:shared", args=[wishlist.share_token])
    expected = list(wishlist.entries.values_list("pk", flat=True))
    first = client.get(url)
    second = client.get(url, {"page": 2})
    assert [entry.pk for entry in first.context["entries"]] == expected[:20]
    assert [entry.pk for entry in second.context["entries"]] == expected[20:]
    assert b"Next" in first.content
    assert b"Previous" in second.content
    wishlist.entries.first().delete()
    assert client.get(url).context["page_obj"].paginator.count == 21


@pytest.mark.parametrize("deleted", ["product", "wishlist", "account"])
def test_shared_deletion_and_generic_unavailable(client, customer, product, deleted):
    wishlist = Wishlist.for_user(customer)
    wishlist.add(product)
    wishlist.enable_sharing()
    url = reverse("wishlist:shared", args=[wishlist.share_token])
    {"product": product, "wishlist": wishlist, "account": customer}[deleted].delete()
    response = client.get(url)
    if deleted == "product":
        assert response.status_code == 200
        assert b"No products saved" in response.content
        assert reverse("products:catalog").encode() in response.content
        wishlist.refresh_from_db()
        assert wishlist.share_token
    else:
        invalid = client.get(reverse("wishlist:shared", args=["invalid-token"]))
        assert response.status_code == invalid.status_code == 404
        assert re.sub(
            rb'"X-CSRFToken": "[^"]+"', b'"X-CSRFToken": ""', response.content
        ) == re.sub(rb'"X-CSRFToken": "[^"]+"', b'"X-CSRFToken": ""', invalid.content)
        assert b"Wishlist unavailable" in response.content
        assert reverse("products:catalog").encode() in response.content


def test_revoked_and_invalid_links_are_indistinguishable(client, customer):
    wishlist = Wishlist.for_user(customer)
    wishlist.enable_sharing()
    url = reverse("wishlist:shared", args=[wishlist.share_token])
    wishlist.disable_sharing()
    revoked = client.get(url)
    invalid = client.get(reverse("wishlist:shared", args=["invalid-token"]))
    assert revoked.status_code == invalid.status_code == 404
    assert re.sub(
        rb'"X-CSRFToken": "[^"]+"', b'"X-CSRFToken": ""', revoked.content
    ) == re.sub(rb'"X-CSRFToken": "[^"]+"', b'"X-CSRFToken": ""', invalid.content)


def test_token_does_not_authorize_private_access_or_mutations(
    client, customer, staff_user, product
):
    wishlist = Wishlist.for_user(customer)
    wishlist.add(product)
    wishlist.enable_sharing()
    data = {
        "token": wishlist.share_token,
        "owner": customer.pk,
        "wishlist": wishlist.pk,
    }
    for name in ("save", "remove", "add_to_cart"):
        assert (
            client.post(
                reverse(f"wishlist:{name}", args=[product.pk]), data
            ).status_code
            == 302
        )
    assert client.get(reverse("wishlist:detail"), data).status_code == 302
    client.force_login(staff_user)
    page = client.get(reverse("wishlist:detail"), data)
    assert b"Your wishlist is empty" in page.content
    client.post(reverse("wishlist:remove", args=[product.pk]), data)
    assert (
        client.post(
            reverse("wishlist:add_to_cart", args=[product.pk]), data
        ).status_code
        == 404
    )
    assert wishlist.entries.count() == 1
