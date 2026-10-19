import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from html import unescape
from time import sleep
from urllib.parse import parse_qs, urlsplit

import pytest
from django.db import (
    IntegrityError,
    OperationalError,
    close_old_connections,
    transaction,
)
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from .models import Wishlist, WishlistEntry


@pytest.mark.parametrize("surface", ["catalog", "category", "detail"])
def test_wired_htmx_control_supports_save_remove_and_save_again(
    client, customer, product, category, surface
):
    destination = {
        "catalog": reverse("products:catalog") + "?q=Seraphine",
        "category": category.get_absolute_url(),
        "detail": product.get_absolute_url(),
    }[surface]
    client.force_login(customer)
    response = client.get(destination)
    for action, count, next_action in [
        ("save", 1, "remove"),
        ("remove", 0, "save"),
        ("save", 1, "remove"),
    ]:
        html = response.content.decode()
        assert f'id="wishlist-control-{product.pk}"' in html
        assert 'hx-target="this" hx-swap="outerHTML"' in html
        assert f'hx-post="{mutation(action, product)}"' in html
        response = client.post(
            mutation(action, product),
            {"next": destination},
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        html = unescape(response.content.decode())
        assert "<html" not in html.lower()
        assert f'hx-post="{mutation(next_action, product)}"' in html
        assert f'name="next" value="{destination}"' in html
        assert response.context["wishlist_item_count"] == count
        assert WishlistEntry.objects.filter(wishlist__user=customer).count() == count


def test_owner_removal_forms_target_list_before_and_after_partial_update(
    client, customer, paginated_wishlist
):
    client.force_login(customer)
    destination = reverse("wishlist:detail") + "?page=2"
    response = client.get(destination)
    for _ in range(2):
        html = response.content.decode()
        assert 'hx-target="#wishlist-contents" hx-swap="outerHTML"' in html
        entry = response.context["entries"][0]
        assert f'hx-post="{mutation("remove", entry.product)}"' in html
        response = client.post(
            mutation("remove", entry.product),
            {"next": destination},
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
    assert response.context["page_obj"].number == 1


def test_htmx_save_updates_control_count_and_preserves_original_save(
    client, customer, product
):
    client.force_login(customer)
    destination = product.get_absolute_url()
    response = client.post(
        mutation("save", product),
        {"next": destination},
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    entry = WishlistEntry.objects.get(wishlist__user=customer, product=product)
    original_saved_at = entry.saved_at

    for result in [
        response,
        client.post(
            mutation("save", product),
            {"next": destination},
            HTTP_HX_REQUEST="true",
        ),
    ]:
        assert result.status_code == 200
        html = result.content.decode()
        assert "<!doctype" not in html.lower()
        assert "<html" not in html.lower()
        assert f'action="{mutation("remove", product)}"' in html
        assert re.search(r">\s*Saved\s*</button>", html)
        assert f'name="next" value="{destination}"' in html
        assert re.search(
            r'<span\b(?=[^>]*\bid="wishlist-count")'
            r'(?=[^>]*\bhx-swap-oob="true")[^>]*>\s*1\s*</span>',
            html,
        )

    entry.refresh_from_db()
    assert entry.saved_at == original_saved_at
    assert WishlistEntry.objects.filter(wishlist__user=customer).count() == 1


def test_htmx_save_reports_availability_change_without_saving(
    client, customer, product
):
    client.force_login(customer)
    destination = product.get_absolute_url()
    initial = client.get(destination)
    assert b"Save to wishlist" in initial.content
    assert initial.context["wishlist_item_count"] == 0

    product.is_available = False
    product.save(update_fields=["is_available"])
    response = client.post(
        mutation("save", product),
        {"next": destination},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    html = response.content.decode()
    assert "<html" not in html.lower()
    assert re.search(
        r'role="alert"[^>]*>\s*This product is no longer available '
        r"and could not be saved\.\s*</[^>]+>",
        html,
    )
    assert not re.search(r">\s*Saved\s*</button>", html)
    assert f'action="{mutation("remove", product)}"' not in html
    assert re.search(
        r'<span\b(?=[^>]*\bid="wishlist-count")'
        r'(?=[^>]*\bhx-swap-oob="true")[^>]*>\s*0\s*</span>',
        html,
    )
    assert not WishlistEntry.objects.filter(
        wishlist__user=customer, product=product
    ).exists()


def test_htmx_owner_removal_recovers_pages_and_final_empty_state(
    client, customer, paginated_wishlist
):
    client.force_login(customer)
    destination = reverse("wishlist:detail") + "?page=2"
    entries = list(paginated_wishlist.entries.all())
    # Remove the two entries on page 2, then all remaining entries. The
    # original page-2 destination must remain usable throughout.
    removal_order = [*entries[20:], *entries[:20]]
    for index, entry in enumerate(removal_order):
        response = client.post(
            mutation("remove", entry.product),
            {"next": destination},
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        remaining = 21 - index
        html = response.content.decode()
        assert "<html" not in html.lower()
        assert '<div id="wishlist-contents"' in html
        assert not paginated_wishlist.entries.filter(pk=entry.pk).exists()
        assert re.search(
            r'<span\b(?=[^>]*\bid="wishlist-count")'
            r'(?=[^>]*\bhx-swap-oob="true")[^>]*>\s*' + str(remaining) + r"\s*</span>",
            html,
        )
        if remaining == 21:
            assert response.context["page_obj"].number == 2
            assert len(response.context["entries"]) == 1
            assert "Page 2 of 2" in html
            assert "Previous</a>" in html
        elif remaining:
            assert response.context["page_obj"].number == 1
            assert len(response.context["entries"]) == remaining
            assert "Wishlist pages" not in html
        else:
            assert "Your wishlist is empty" in html
            assert "Browse products" in html
            assert "Wishlist pages" not in html


def test_owner_wishlist_paginates_with_stable_newest_first_order(
    client, customer, category
):
    from products.models import Product

    wishlist = Wishlist.for_user(customer)
    entries = []
    for number in range(22):
        product = Product.objects.create(
            name=f"Saved product {number}",
            slug=f"saved-product-{number}",
            price="10.00",
            category=category,
        )
        entries.append(wishlist.add(product))
    tied_time = timezone.now() - timedelta(days=1)
    wishlist.entries.update(saved_at=tied_time)
    # The oldest-created entry is the newest save; all other save times tie.
    wishlist.entries.filter(pk=entries[0].pk).update(saved_at=timezone.now())
    expected = [entries[0], *reversed(entries[1:])]

    client.force_login(customer)
    first_page = client.get(reverse("wishlist:detail"))
    assert first_page.status_code == 200
    assert list(first_page.context["entries"]) == expected[:20]
    assert first_page.context["page_obj"].has_next()

    second_page = client.get(reverse("wishlist:detail"), {"page": 2})
    assert second_page.status_code == 200
    assert list(second_page.context["entries"]) == expected[20:]
    assert second_page.context["page_obj"].has_previous()
    assert not second_page.context["page_obj"].has_next()


def test_removal_recovers_last_page_and_final_entry_empty_state(
    client, customer, category
):
    from products.models import Product

    wishlist = Wishlist.for_user(customer)
    products = [
        Product.objects.create(
            name=f"Removal product {number}",
            slug=f"removal-product-{number}",
            price="10.00",
            category=category,
        )
        for number in range(21)
    ]
    for product in products:
        wishlist.add(product)
    client.force_login(customer)
    detail_url = reverse("wishlist:detail")
    last_page_url = detail_url + "?page=2"
    last_page = client.get(last_page_url)
    assert last_page.status_code == 200
    last_entry = list(last_page.context["entries"])[0]

    response = client.post(
        mutation("remove", last_entry.product),
        {"next": last_page_url},
        follow=True,
    )
    assert response.status_code == 200
    assert response.context["page_obj"].number == 1
    assert len(response.context["entries"]) == 20
    assert not wishlist.entries.filter(pk=last_entry.pk).exists()

    for product in products:
        if product.pk == last_entry.product_id:
            continue
        response = client.post(
            mutation("remove", product),
            {"next": detail_url + "?page=1"},
            follow=True,
        )
        assert response.status_code == 200
    assert not wishlist.entries.exists()
    assert b"Your wishlist is empty" in response.content
    links = re.findall(r"<a\b[^>]*>.*?</a>", response.content.decode(), re.S)
    wishlist_links = [link for link in links if f'href="{detail_url}"' in link]
    assert any(
        re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", link)).strip() == "Wishlist 0"
        for link in wishlist_links
    )


def mutation(action, product):
    return reverse(f"wishlist:{action}", args=[product.pk])


def test_catalog_category_wishlist_forms_follow_current_account(
    client, customer, staff_user, product, category
):
    Wishlist.for_user(staff_user).add(product)
    destinations = [
        reverse("products:catalog") + "?q=Seraphine",
        reverse("products:category", args=[category.slug]) + "?q=Seraphine",
    ]
    for destination in destinations:
        for account, initially_saved in [(customer, False), (staff_user, True)]:
            client.force_login(account)
            for saved in [initially_saved, not initially_saved]:
                response = client.get(destination)
                assert response.status_code == 200
                action = "remove" if saved else "save"
                label = "Saved" if saved else "Save to wishlist"
                forms = re.findall(
                    r"<form\b[^>]*>.*?</form>", response.content.decode(), re.S
                )
                matching = [
                    form
                    for form in forms
                    if f'action="{mutation(action, product)}"' in form
                ]
                assert len(matching) == 1, (
                    f"Expected one {action} wishlist form at {destination} "
                    f"for {account.username}"
                )
                form = unescape(matching[0])
                assert 'method="post"' in form.lower()
                assert re.search(rf">\s*{label}\s*</button>", form)
                assert f'name="next" value="{destination}"' in form
                response = client.post(
                    mutation(action, product), {"next": destination}, follow=True
                )
                assert response.redirect_chain == [(destination, 302)]
                assert (
                    WishlistEntry.objects.filter(
                        wishlist__user=account, product=product
                    ).exists()
                    is not saved
                )
            assert (
                WishlistEntry.objects.filter(
                    wishlist__user=account, product=product
                ).exists()
                is initially_saved
            )


@pytest.mark.parametrize("listing", ["catalog", "category"])
def test_signed_out_card_login_returns_to_product_without_saving(
    client, customer, product, category, listing
):
    destination = (
        reverse("products:catalog")
        if listing == "catalog"
        else reverse("products:category", args=[category.slug])
    )
    response = client.get(destination)
    links = re.findall(
        r'<a\b[^>]*href="([^"]+)"[^>]*>\s*Sign in to save\s*</a>',
        response.content.decode(),
    )
    assert len(links) == 1
    login_url = unescape(links[0])
    assert urlsplit(login_url).path == reverse("accounts:login")
    assert parse_qs(urlsplit(login_url).query)["next"] == [product.get_absolute_url()]
    response = client.post(
        login_url,
        {
            "username": customer.username,
            "password": "customer123",
            "next": product.get_absolute_url(),
        },
        follow=True,
    )
    assert response.redirect_chain == [(product.get_absolute_url(), 302)]
    assert b"Save to wishlist" in response.content
    assert not Wishlist.objects.exists()


@pytest.mark.parametrize("role", ["customer", "staff", "admin"])
def test_navbar_zero_count_does_not_create_wishlist(client, customer, role):
    customer.is_staff = role != "customer"
    customer.is_superuser = role == "admin"
    customer.save()
    client.force_login(customer)
    response = client.get(reverse("products:catalog"))
    assert response.context["wishlist_item_count"] == 0
    assert re.search(
        rf'<a href="{reverse("wishlist:detail")}"[^>]*>\s*Wishlist\s*'
        r"<span[^>]*>0</span>",
        response.content.decode(),
    )
    assert not Wishlist.objects.exists()


def test_navbar_counts_all_pages_unavailable_and_deletions(
    client, customer, staff_user, paginated_wishlist
):
    unavailable = paginated_wishlist.entries.first().product
    unavailable.is_available = False
    unavailable.save()
    client.force_login(customer)
    detail_url = reverse("wishlist:detail")
    for page in [1, 2]:
        response = client.get(detail_url, {"page": page})
        assert response.context["wishlist_item_count"] == 22
    assert b"Unavailable" in client.get(detail_url).content
    client.force_login(staff_user)
    assert client.get(detail_url).context["wishlist_item_count"] == 0
    assert not Wishlist.objects.filter(user=staff_user).exists()
    client.force_login(customer)
    unavailable.delete()
    assert client.get(detail_url).context["wishlist_item_count"] == 21
    paginated_wishlist.delete()
    response = client.get(detail_url)
    assert response.context["wishlist_item_count"] == 0
    assert b"Your wishlist is empty" in response.content
    assert not Wishlist.objects.filter(user=customer).exists()


def test_visible_pagination_and_removal_forms_preserve_current_page(
    client, customer, paginated_wishlist
):
    client.force_login(customer)
    detail_url = reverse("wishlist:detail")
    response = client.get(detail_url)
    assert re.search(r'<a href="\?page=2"[^>]*>Next</a>', response.content.decode())
    response = client.get(detail_url, {"page": 2})
    assert b"Page 2 of 2" in response.content
    assert re.search(r'<a href="\?page=1"[^>]*>Previous</a>', response.content.decode())
    for remaining_count in [1, 20]:
        # The first POST in the site shell is logout; select a wishlist removal.
        forms = re.findall(
            r'<form method="post" action="([^"]+)"[^>]*>(.*?)</form>',
            response.content.decode(),
            re.S,
        )
        action, body = next(
            (action, body)
            for action, body in forms
            if action.startswith(reverse("wishlist:detail"))
        )
        destination = unescape(re.search(r'name="next" value="([^"]+)"', body)[1])
        assert destination == detail_url + "?page=2"
        response = client.post(action, {"next": destination}, follow=True)
        assert response.status_code == 200
        assert len(response.context["entries"]) == remaining_count
    assert response.context["page_obj"].number == 1
    assert b"Wishlist pages" not in response.content


@pytest.mark.parametrize("listing", ["catalog", "category"])
def test_card_mutations_preserve_filtered_page_and_update_navbar(
    client, customer, category, paginated_wishlist, listing
):
    client.force_login(customer)
    listing_url = (
        reverse("products:catalog")
        if listing == "catalog"
        else reverse("products:category", args=[category.slug])
    )
    destination = listing_url + "?q=Wishlist&page=2"
    response = client.get(destination)
    product = response.context["products"][0]
    for action, count, label in [
        ("remove", 21, "Save to wishlist"),
        ("save", 22, "Saved"),
    ]:
        response = client.post(
            mutation(action, product), {"next": destination}, follow=True
        )
        assert response.redirect_chain == [(destination, 302)]
        assert response.context["wishlist_item_count"] == count
        forms = re.findall(r"<form\b[^>]*>.*?</form>", response.content.decode(), re.S)
        next_action = "save" if action == "remove" else "remove"
        form = next(
            form
            for form in forms
            if f'action="{mutation(next_action, product)}"' in form
        )
        assert f'name="next" value="{destination.replace("&", "&amp;")}"' in form
        assert re.search(rf">\s*{label}\s*</button>", form)
        assert f'hx-post="{mutation(next_action, product)}"' in form


@pytest.mark.parametrize("role", ["customer", "staff", "admin"])
def test_detail_save_remove_journey(client, customer, product, role, mailoutbox):
    customer.is_staff = role != "customer"
    customer.is_superuser = role == "admin"
    customer.save()
    assert not customer.email_verified
    client.force_login(customer)
    response = client.get(product.get_absolute_url())
    assert b"Save to wishlist" in response.content
    for _ in range(2):
        response = client.post(
            mutation("save", product), {"next": product.get_absolute_url()}
        )
        assert response.url == product.get_absolute_url()
    entry = WishlistEntry.objects.get(wishlist__user=customer)
    saved_at = entry.saved_at
    client.post(mutation("save", product))
    entry.refresh_from_db()
    assert entry.saved_at == saved_at
    assert b">Saved</button>" in client.get(product.get_absolute_url()).content
    response = client.get(reverse("wishlist:detail"))
    assert list(response.context["entries"]) == [entry]
    assert product.name.encode() in response.content
    client.post(mutation("remove", product))
    client.post(mutation("remove", product))
    assert not WishlistEntry.objects.exists()
    assert b"Your wishlist is empty" in client.get(reverse("wishlist:detail")).content
    client.post(mutation("save", product))
    assert WishlistEntry.objects.get().saved_at > saved_at
    assert not mailoutbox


def test_persistence_and_live_unavailable_data(client, customer, product):
    wishlist = Wishlist.for_user(customer)
    entry = wishlist.add(product)
    product.name = "Updated product"
    product.price = "987.65"
    product.is_available = False
    product.save()
    other_device = Client()
    other_device.force_login(customer)
    response = other_device.get(reverse("wishlist:detail"))
    assert b"Updated product" in response.content
    assert b"987.65" in response.content
    assert b"Unavailable" in response.content
    assert product.catalog_image_url.encode() in response.content
    assert b">Saved</button>" in other_device.get(product.get_absolute_url()).content
    assert wishlist.add(product).saved_at == entry.saved_at
    other_device.post(mutation("remove", product))
    assert not wishlist.entries.exists()


def test_availability_rechecked_and_deleted_product(client, customer, product):
    client.force_login(customer)
    client.get(product.get_absolute_url())
    product.is_available = False
    product.save()
    response = client.post(mutation("save", product), follow=True)
    assert b"no longer available" in response.content
    assert not WishlistEntry.objects.exists()
    assert b"Save to wishlist" not in client.get(product.get_absolute_url()).content
    save_url = mutation("save", product)
    product.delete()
    assert client.post(save_url).status_code == 404


@pytest.mark.parametrize("htmx", [False, True])
def test_owner_isolation_and_no_creation_on_read(
    client, customer, staff_user, product, htmx
):
    owner_list = Wishlist.for_user(customer)
    original = owner_list.add(product)
    client.force_login(staff_user)
    response = client.get(reverse("wishlist:detail"), {"user": customer.pk})
    assert not response.context["entries"]
    assert not Wishlist.objects.filter(user=staff_user).exists()
    data = {"user": customer.pk, "wishlist": owner_list.pk, "owner": customer.pk}
    headers = {"HX-Request": "true"} if htmx else {}
    client.post(mutation("remove", product), data, headers=headers)
    assert WishlistEntry.objects.filter(pk=original.pk).exists()
    client.post(mutation("save", product), data, headers=headers)
    assert WishlistEntry.objects.filter(wishlist__user=staff_user).count() == 1
    assert owner_list.entries.count() == 1


@pytest.mark.parametrize("action", ["save", "remove"])
@pytest.mark.parametrize("htmx", [False, True])
def test_post_and_csrf_required(client, customer, product, action, htmx):
    entry = Wishlist.for_user(customer).add(product)
    client.force_login(customer)
    headers = {"HX-Request": "true"} if htmx else {}
    assert client.get(mutation(action, product), headers=headers).status_code == 405
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(customer)
    assert (
        csrf_client.post(mutation(action, product), headers=headers).status_code == 403
    )
    assert WishlistEntry.objects.filter(pk=entry.pk).exists()
    page = csrf_client.get(product.get_absolute_url())
    assert b"csrfmiddlewaretoken" in page.content
    assert csrf_client.post(
        mutation(action, product),
        {"csrfmiddlewaretoken": csrf_client.cookies["csrftoken"].value},
        headers=headers,
    ).status_code == (200 if htmx else 302)


@pytest.mark.parametrize(
    "destination",
    [
        "https://evil.test/",
        "//evil.test/",
        "/\\evil.test/",
        "javascript:alert(1)",
        "relative",
    ],
)
@pytest.mark.parametrize("htmx", [False, True])
def test_external_returns_rejected(client, customer, product, destination, htmx):
    client.force_login(customer)
    response = client.post(
        mutation("save", product),
        {"next": destination},
        headers={"HX-Request": "true"} if htmx else {},
    )
    if htmx:
        assert response.status_code == 200
        assert response.context["return_url"] == reverse("wishlist:detail")
    else:
        assert response.url == reverse("wishlist:detail")


@pytest.mark.parametrize("htmx", [False, True])
@pytest.mark.parametrize("action", ["save", "remove"])
def test_expired_session_login_never_replays(
    client, customer, staff_user, product, htmx, action
):
    original = Wishlist.for_user(customer).add(product)
    client.force_login(customer)
    client.logout()
    response = client.post(
        mutation(action, product),
        {"next": product.get_absolute_url()},
        headers={"HX-Request": "true"} if htmx else {},
    )
    login_url = response.headers["HX-Redirect"] if htmx else response.url
    assert response.status_code == (200 if htmx else 302)
    assert urlsplit(login_url).path == reverse("accounts:login")
    assert parse_qs(urlsplit(login_url).query)["next"] == [product.get_absolute_url()]
    response = client.post(
        login_url,
        {
            "username": staff_user.username,
            "password": "employee123",
            "next": product.get_absolute_url(),
        },
        follow=True,
    )
    assert response.status_code == 200
    assert WishlistEntry.objects.get().pk == original.pk
    assert not Wishlist.objects.filter(user=staff_user).exists()


def test_anonymous_links_and_private_page(client, product):
    response = client.get(product.get_absolute_url())
    assert b"Sign in to save" in response.content
    assert b"next=/products/seraphine-home-hub/" in response.content
    assert client.get(reverse("wishlist:detail")).status_code == 302
    assert not Wishlist.objects.exists()


def test_database_uniqueness(customer, product):
    wishlist = Wishlist.for_user(customer)
    wishlist.add(product)
    with pytest.raises(IntegrityError), transaction.atomic():
        Wishlist.objects.create(user=customer)
    with pytest.raises(IntegrityError), transaction.atomic():
        WishlistEntry.objects.create(wishlist=wishlist, product=product)


@pytest.mark.parametrize("deleted", ["user", "wishlist", "product"])
def test_cascades(customer, product, deleted):
    wishlist = Wishlist.for_user(customer)
    wishlist.add(product)
    {"user": customer, "wishlist": wishlist, "product": product}[deleted].delete()
    assert not WishlistEntry.objects.exists()
    if deleted != "product":
        assert not Wishlist.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_saves(customer, product):
    wishlist = Wishlist.for_user(customer)
    wishlist_pk, product_pk = wishlist.pk, product.pk

    def save():
        close_old_connections()
        try:
            # Shared-cache SQLite test databases report SQLITE_LOCKED rather
            # than waiting for the writer as file-backed SQLite does. Retry
            # those transactions; each successful save must keep the same row.
            for attempt in range(30):
                try:
                    current = Wishlist.objects.get(pk=wishlist_pk)
                    return current.add(product).pk
                except OperationalError as error:
                    if "locked" not in str(error).lower() or attempt == 29:
                        raise
                    sleep(0.01)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(lambda _: save(), range(8)))
    entry = WishlistEntry.objects.get(product_id=product_pk)
    assert set(ids) == {entry.pk}
    timestamp = entry.saved_at
    wishlist.add(product)
    entry.refresh_from_db()
    assert entry.saved_at == timestamp
    assert timestamp <= timezone.now()
