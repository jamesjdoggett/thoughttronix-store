"""Purchase eligibility for product reviews."""

from urllib.parse import urlencode

from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count, Q
from django.http import Http404
from django.urls import reverse
from django.utils.dateparse import parse_datetime

from orders.models import Order, OrderItem

from .models import Review


def can_review(user, product) -> bool:
    """Return whether this account has a qualifying purchase of this product."""
    if not user.is_authenticated:
        return False
    return OrderItem.objects.filter(
        order__user=user,
        order__status__in=(
            Order.Status.PLACED,
            Order.Status.SHIPPED,
            Order.Status.DELIVERED,
        ),
        product=product,
    ).exists()


def publish_review(user, product, *, rating: int, comment: str) -> Review:
    """Publish once for an eligible account, including racing submissions."""
    if not can_review(user, product):
        raise PermissionDenied("A qualifying purchase is required.")
    review, created = Review.objects.get_or_create(
        author=user,
        product=product,
        defaults={"rating": rating, "comment": comment},
    )
    if not created:
        raise ValueError("You already have a review for this product.")
    return review


def review_context(product, user, cursor=None) -> dict:
    """Collect a stable older batch, all-review totals, and author controls."""
    reviews = product.reviews.select_related("author")
    own_review = reviews.filter(author=user).first() if user.is_authenticated else None
    page = reviews
    if cursor:
        try:
            boundary = signing.loads(cursor, salt="product-review-page")
            posted_at = parse_datetime(boundary["created_at"])
            pk = int(boundary["pk"])
            if posted_at is None or boundary["product"] != product.pk:
                raise ValueError
        except (signing.BadSignature, ValueError, TypeError, KeyError):
            raise Http404("Invalid review page.") from None
        page = page.filter(
            Q(created_at__lt=posted_at) | Q(created_at=posted_at, pk__lt=pk)
        )
    batch = list(page[:11])
    next_url = None
    if len(batch) > 10:
        last = batch[9]
        next_cursor = signing.dumps(
            {
                "product": product.pk,
                "created_at": last.created_at.isoformat(),
                "pk": last.pk,
            },
            salt="product-review-page",
        )
        next_url = (
            reverse("products:review_list", args=[product.slug])
            + "?"
            + urlencode({"cursor": next_cursor})
            + "#reviews"
        )
    return {
        "product": product,
        "reviews": batch[:10],
        "review_next_url": next_url,
        "review_summary": reviews.aggregate(average=Avg("rating"), count=Count("pk")),
        "own_review": own_review,
        "can_create_review": own_review is None and can_review(user, product),
    }
