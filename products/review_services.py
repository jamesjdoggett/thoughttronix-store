"""Purchase eligibility for product reviews."""

from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count

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


def review_context(product, user) -> dict:
    """Collect saved review displays and current creation eligibility."""
    reviews = product.reviews.select_related("author")
    own_review = reviews.filter(author=user).first() if user.is_authenticated else None
    return {
        "product": product,
        "reviews": reviews[:10],
        "review_summary": reviews.aggregate(average=Avg("rating"), count=Count("pk")),
        "own_review": own_review,
        "can_create_review": own_review is None and can_review(user, product),
    }
