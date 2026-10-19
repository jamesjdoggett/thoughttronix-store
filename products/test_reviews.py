"""Customer review behavior on public product pages."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError, transaction
from django.db.models.query import QuerySet
from django.test import Client
from django.urls import reverse

from orders.models import Order, OrderItem

from .forms import ReviewForm
from .models import Review
from .review_services import can_review


@pytest.mark.parametrize(
    ("statuses", "actor", "expected"),
    [
        ([Order.Status.PLACED], "purchaser", True),
        ([Order.Status.SHIPPED], "purchaser", True),
        ([Order.Status.DELIVERED], "purchaser", True),
        ([Order.Status.CANCELLED], "purchaser", False),
        ([Order.Status.CANCELLED, Order.Status.PLACED], "purchaser", True),
        ([], "purchaser", False),
        ([Order.Status.PLACED], "recipient", False),
        ([Order.Status.PLACED], "anonymous", False),
        ([Order.Status.PLACED], "staff_purchaser", True),
        ([], "staff_purchaser", False),
    ],
)
def test_review_eligibility_requires_own_qualifying_purchase(
    customer, staff_user, unavailable_product, statuses, actor, expected
):
    # SoulSear has the same rules, including when unavailable. Matching shipping
    # identity and contact email do not confer rights on a recipient/next of kin.
    product = unavailable_product
    product.name = "SoulSear Mark I"
    product.save(update_fields=["name"])
    purchaser = staff_user if actor == "staff_purchaser" else customer
    recipient = staff_user
    for status in statuses:
        order = Order.objects.create(
            user=purchaser,
            status=status,
            total=product.price,
            email=recipient.email,
            shipping_name=recipient.username,
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            unit_price=product.price,
            quantity=1,
        )
    user = {
        "purchaser": customer,
        "recipient": recipient,
        "anonymous": AnonymousUser(),
        "staff_purchaser": staff_user,
    }[actor]

    assert can_review(user, product) is expected


@pytest.mark.parametrize("is_author", [True, False])
def test_only_author_can_edit_review_after_purchase_cancellation(
    client, customer, staff_user, product, review_purchase, is_author
):
    staff_user.is_staff = False
    staff_user.save(update_fields=["is_staff"])
    review = Review.objects.create(
        product=product, author=customer, rating=2, comment="Original feedback"
    )
    posted_at = review.created_at
    review_purchase.status = Order.Status.CANCELLED
    review_purchase.save(update_fields=["status"])
    product.is_available = False
    product.save(update_fields=["is_available"])
    client.force_login(customer if is_author else staff_user)
    url = reverse(
        "products:review_edit", kwargs={"slug": product.slug, "pk": review.pk}
    )

    opened = client.get(url)
    saved = client.post(url, {"rating": "5", "comment": "  Revised feedback  "})
    review.refresh_from_db()

    assert review.rating == (5 if is_author else 2)
    assert review.comment == ("Revised feedback" if is_author else "Original feedback")
    assert review.author == customer
    assert review.created_at == posted_at
    assert opened.status_code == (200 if is_author else 403)
    assert saved.status_code == (302 if is_author else 403)
    if is_author:
        assert saved.url == product.get_absolute_url() + "#reviews"


@pytest.mark.parametrize("still_qualifies", [True, False])
def test_deletion_allows_replacement_only_with_current_qualifying_purchase(
    client, customer, product, review_purchase, still_qualifies
):
    review = Review.objects.create(
        product=product, author=customer, rating=2, comment="Original feedback"
    )
    if not still_qualifies:
        review_purchase.status = Order.Status.CANCELLED
        review_purchase.save(update_fields=["status"])
    client.force_login(customer)
    delete_url = reverse(
        "products:review_delete", kwargs={"slug": product.slug, "pk": review.pk}
    )
    create_url = reverse("products:review_create", kwargs={"slug": product.slug})

    confirmation = client.get(delete_url)
    assert confirmation.status_code == 200
    assert Review.objects.filter(pk=review.pk).exists()

    deleted = client.post(delete_url)
    assert deleted.status_code == 302
    assert deleted.url == product.get_absolute_url() + "#reviews"
    assert not Review.objects.filter(pk=review.pk).exists()

    replacement = client.post(create_url, {"rating": "4", "comment": "Replacement"})
    assert replacement.status_code == (302 if still_qualifies else 403)
    assert Review.objects.filter(author=customer, product=product).count() == int(
        still_qualifies
    )
    if still_qualifies:
        new_review = Review.objects.get(author=customer, product=product)
        assert new_review.pk != review.pk
        assert (new_review.rating, new_review.comment) == (4, "Replacement")
        repeated = client.post(
            create_url, {"rating": "1", "comment": "Repeated submission"}
        )
        assert repeated.status_code == 200
        assert "already" in repeated.content.decode().lower()
        assert Review.objects.filter(author=customer, product=product).count() == 1
        new_review.refresh_from_db()
        assert (new_review.rating, new_review.comment) == (4, "Replacement")


@pytest.mark.parametrize("enhanced", [True, False])
def test_publication_and_edit_responses_synchronize_saved_displays(
    client, customer, product, review_purchase, enhanced
):
    client.force_login(customer)
    headers = {"HTTP_HX_REQUEST": "true"} if enhanced else {}
    create = reverse("products:review_create", args=[product.slug])
    response = client.post(
        create,
        {"rating": "4", "comment": "  <b>Feedback</b>\nSecond line  "},
        **headers,
    )
    review = Review.objects.get(author=customer, product=product)
    assert review.comment == "<b>Feedback</b>\nSecond line"
    assert response.status_code == (200 if enhanced else 302)
    if enhanced:
        page = response.content.decode()
        assert response["HX-Reswap"] == "none"
        assert 'hx-swap-oob="afterbegin:#review-list"' in page
        assert f'id="review-own-{review.pk}"' in page
        assert f'id="review-public-{review.pk}"' in page
        assert 'id="review-summary"' in page
        assert "4.0 out of 5 stars" in page
        assert "&lt;b&gt;Feedback&lt;/b&gt;<br>Second line" in page
        assert "<html" not in page
    else:
        assert response.url == product.get_absolute_url() + "#reviews"

    edit = reverse("products:review_edit", args=[product.slug, review.pk])
    saved = client.post(
        edit, {"rating": "2", "comment": "Updated", "location": "public"}, **headers
    )
    review.refresh_from_db()
    assert (review.rating, review.comment, review.revision) == (2, "Updated", 2)
    if enhanced:
        page = saved.content.decode()
        assert page.count("Updated") == 2
        assert "2.0 out of 5 stars" in page
        assert f'id="review-public-{review.pk}"' in page
        assert "afterbegin:#review-list" not in page
        assert 'id="review-list"' not in page


@pytest.mark.parametrize("rating", ["", "0", "6", "2.5", "abc"])
def test_review_rating_validation(rating):
    form = ReviewForm({"rating": rating, "comment": "Feedback"})
    assert not form.is_valid()
    assert "rating" in form.errors


@pytest.mark.parametrize(
    "comment,valid",
    [
        ("", False),
        (" \n\t ", False),
        ("a", True),
        ("a" * 2000, True),
        ("a" * 2001, False),
        ("  " + "a" * 2000 + "  ", True),
    ],
)
def test_review_comment_validation(db, comment, valid):
    form = ReviewForm({"rating": "3", "comment": comment})
    assert form.is_valid() is valid
    if valid:
        assert form.cleaned_data["comment"] == comment.strip()
    else:
        assert "comment" in form.errors


@pytest.mark.parametrize("enhanced", [True, False])
@pytest.mark.parametrize("editing", [True, False])
def test_invalid_review_retains_fields_and_saved_state(
    client, customer, product, review_purchase, enhanced, editing
):
    client.force_login(customer)
    if editing:
        review = Review.objects.create(
            author=customer, product=product, rating=4, comment="Saved"
        )
        url = reverse("products:review_edit", args=[product.slug, review.pk])
    else:
        url = reverse("products:review_create", args=[product.slug])
    response = client.post(
        url,
        {"rating": "6", "comment": "Draft retained", "location": "public"},
        **({"HTTP_HX_REQUEST": "true"} if enhanced else {}),
    )
    page = response.content.decode()
    assert response.status_code == 200
    assert 'value="6"' in page
    assert "Draft retained" in page
    assert "Ensure this value is less than or equal to 5." in page
    assert ("<html" in page) is (not enhanced)
    assert "hx-swap-oob=" not in page
    if editing:
        review.refresh_from_db()
        assert (review.rating, review.comment) == (4, "Saved")
    else:
        assert not product.reviews.exists()


@pytest.mark.parametrize(
    "status,allowed",
    [
        (Order.Status.PLACED, True),
        (Order.Status.SHIPPED, True),
        (Order.Status.DELIVERED, True),
        (Order.Status.CANCELLED, False),
    ],
)
@pytest.mark.parametrize("staff", [True, False])
def test_creation_endpoint_enforces_personal_purchase_not_email_verification(
    client, customer, product, review_purchase, status, allowed, staff
):
    customer.is_staff = staff
    customer.email = "unverified@example.com"
    customer.save()
    assert not customer.email_verified
    review_purchase.status = status
    review_purchase.save()
    product.is_available = False
    product.save()
    client.force_login(customer)
    response = client.post(
        reverse("products:review_create", args=[product.slug]),
        {"rating": "5", "comment": "Purchased"},
    )
    assert response.status_code == (302 if allowed else 403)
    assert product.reviews.count() == int(allowed)


@pytest.mark.parametrize("anonymous", [True, False])
def test_nonpurchaser_cannot_publish_even_with_matching_order_contact(
    client, customer, staff_user, product, review_purchase, anonymous
):
    review_purchase.email = "recipient@example.com"
    review_purchase.shipping_name = staff_user.username
    review_purchase.save()
    staff_user.email = review_purchase.email
    staff_user.save()
    if not anonymous:
        client.force_login(staff_user)
    response = client.post(
        reverse("products:review_create", args=[product.slug]),
        {"rating": "5", "comment": "Not my purchase", "author": customer.pk},
    )
    assert response.status_code == (302 if anonymous else 403)
    assert not product.reviews.exists()


def test_public_reviews_limit_stable_order_summary_and_dedicated_old_review(
    client, customer, product
):
    own = Review.objects.create(
        author=customer, product=product, rating=1, comment="Oldest"
    )
    for number in range(11):
        author = get_user_model().objects.create_user(username=f"reviewer{number}")
        Review.objects.create(
            author=author,
            product=product,
            rating=5,
            comment=f"Public {number}",
            created_at=own.created_at,
        )
    response = client.get(product.get_absolute_url())
    reviews = list(response.context["reviews"])
    assert len(reviews) == 10
    assert [review.pk for review in reviews] == sorted(
        [review.pk for review in reviews], reverse=True
    )
    assert own not in reviews
    assert response.context["review_summary"]["count"] == 12
    assert response.context["review_summary"]["average"] == pytest.approx(56 / 12)
    assert "4.7 out of 5 stars" in response.content.decode()
    client.force_login(customer)
    response = client.get(product.get_absolute_url())
    assert response.context["own_review"] == own
    assert f'id="review-own-{own.pk}"' in response.content.decode()
    assert f'id="review-public-{own.pk}"' not in response.content.decode()


def test_empty_reviews_show_count_without_numeric_average(client, product):
    page = client.get(product.get_absolute_url()).content.decode()
    assert "No reviews yet" in page
    assert "0 reviews" in page
    assert "out of 5 stars" not in page


@pytest.mark.parametrize("location", ["own", "public"])
def test_inline_cancel_restores_saved_card_without_mutation(
    client, customer, product, location
):
    review = Review.objects.create(
        author=customer, product=product, rating=4, comment="Saved content"
    )
    client.force_login(customer)
    url = reverse("products:review_edit", args=[product.slug, review.pk])
    opened = client.get(url, {"location": location}, HTTP_HX_REQUEST="true")
    assert f'id="review-{location}-{review.pk}"' in opened.content.decode()
    assert "Save" in opened.content.decode()
    cancelled = client.get(
        url, {"location": location, "cancel": "1"}, HTTP_HX_REQUEST="true"
    )
    assert "Saved content" in cancelled.content.decode()
    assert "<form" not in cancelled.content.decode()
    review.refresh_from_db()
    assert (review.rating, review.comment, review.revision) == (4, "Saved content", 1)
    assert (
        client.get(url, {"cancel": "1"}).url == product.get_absolute_url() + "#reviews"
    )


@pytest.mark.parametrize("eligible", [True, False])
def test_enhanced_delete_updates_both_copies_summary_and_eligibility(
    client, customer, product, review_purchase, eligible
):
    review = Review.objects.create(
        author=customer, product=product, rating=4, comment="Saved content"
    )
    if not eligible:
        review_purchase.status = Order.Status.CANCELLED
        review_purchase.save()
    client.force_login(customer)
    url = reverse("products:review_delete", args=[product.slug, review.pk])
    confirmation = client.get(url, {"location": "public"}, HTTP_HX_REQUEST="true")
    assert "Confirm" in confirmation.content.decode()
    assert "Cancel" in confirmation.content.decode()
    assert Review.objects.filter(pk=review.pk).exists()
    response = client.post(url, HTTP_HX_REQUEST="true")
    page = response.content.decode()
    assert response["HX-Reswap"] == "none"
    assert f'id="review-public-{review.pk}" hx-swap-oob="delete"' in page
    assert f'id="review-own-{review.pk}"' not in page
    assert 'id="your-review"' in page
    assert "0 reviews" in page
    assert "No reviews yet" in page
    assert ("Publish review" in page) is eligible
    assert 'id="review-list"' not in page


@pytest.mark.parametrize("operation", ["edit", "delete"])
def test_management_rejects_other_customer_anonymous_and_wrong_product(
    client, customer, staff_user, product, unavailable_product, operation
):
    review = Review.objects.create(
        author=customer, product=product, rating=3, comment="Saved"
    )
    url = reverse(f"products:review_{operation}", args=[product.slug, review.pk])
    assert client.get(url).status_code == 302
    assert client.post(url, {"rating": "1", "comment": "Hijack"}).status_code == 302
    staff_user.is_staff = False
    staff_user.save()
    client.force_login(staff_user)
    assert client.get(url).status_code == 403
    assert client.post(url, {"rating": "1", "comment": "Hijack"}).status_code == 403
    client.force_login(customer)
    wrong_url = reverse(
        f"products:review_{operation}", args=[unavailable_product.slug, review.pk]
    )
    assert client.get(wrong_url).status_code == 404
    assert client.post(wrong_url).status_code == 404
    review.refresh_from_db()
    assert review.comment == "Saved"


def test_review_mutations_require_csrf(customer, product, review_purchase):
    client = Client(enforce_csrf_checks=True)
    client.force_login(customer)
    review = Review.objects.create(
        author=customer, product=product, rating=3, comment="Saved"
    )
    urls = [reverse("products:review_create", args=[product.slug])]
    urls += [
        reverse(f"products:review_{action}", args=[product.slug, review.pk])
        for action in ("edit", "delete")
    ]
    for url in urls:
        assert (
            client.post(url, {"rating": "4", "comment": "Attempt"}).status_code == 403
        )
    review.refresh_from_db()
    assert review.comment == "Saved"


def test_product_lifecycle_preserves_order_snapshots_not_review_rights(
    client, customer, product, review_purchase
):
    review = Review.objects.create(
        author=customer, product=product, rating=3, comment="Saved"
    )
    product.is_available = False
    product.save()
    assert Review.objects.filter(pk=review.pk).exists()
    assert "Saved" in client.get(product.get_absolute_url()).content.decode()
    assert can_review(customer, product)
    category, slug, name, price = (
        product.category,
        product.slug,
        product.name,
        product.price,
    )
    item = review_purchase.items.get()
    product.delete()
    assert not Review.objects.filter(pk=review.pk).exists()
    item.refresh_from_db()
    assert item.product_id is None
    assert (item.product_name, item.unit_price, item.quantity) == (name, price, 1)
    replacement = category.products.create(name=name, slug=slug, price=price)
    assert not replacement.reviews.exists()
    assert not can_review(customer, replacement)


def test_database_rejects_duplicate_reviews_and_out_of_range_stars(customer, product):
    Review.objects.create(author=customer, product=product, rating=3, comment="Saved")
    with pytest.raises(IntegrityError), transaction.atomic():
        Review.objects.create(
            author=customer, product=product, rating=4, comment="Duplicate"
        )
    for rating in (0, 6):
        with pytest.raises(IntegrityError), transaction.atomic():
            product.reviews.update(rating=rating)
    assert product.reviews.count() == 1
    assert product.reviews.get().rating == 3


def test_concurrent_create_collision_returns_duplicate_feedback(
    client, customer, product, review_purchase, monkeypatch
):
    # Emulate the interleaving at the database boundary: first lookup misses,
    # another request wins, then INSERT collides and Django retrieves the winner.
    winner = Review.objects.create(
        author=customer, product=product, rating=5, comment="Winner"
    )
    original_get = QuerySet.get
    missed = False

    def racing_get(queryset, *args, **kwargs):
        nonlocal missed
        if queryset.model is Review and not missed:
            missed = True
            raise Review.DoesNotExist
        return original_get(queryset, *args, **kwargs)

    monkeypatch.setattr(QuerySet, "get", racing_get)
    client.force_login(customer)
    response = client.post(
        reverse("products:review_create", args=[product.slug]),
        {"rating": "1", "comment": "Losing submission"},
        HTTP_HX_REQUEST="true",
    )
    assert missed
    assert response.status_code == 200
    assert "already have a review" in response.content.decode()
    assert "Losing submission" in response.content.decode()
    assert product.reviews.count() == 1
    winner.refresh_from_db()
    assert (winner.rating, winner.comment) == (5, "Winner")
