"""Order placement — one of the codebase's two deliberate deep modules.

The interface is the product: one function that turns a cart and a
validated checkout into an order, all-or-nothing. Callers never touch
``Order`` construction directly.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.core import signing
from django.db import transaction
from django.db.models import F

from .models import Cart, CartItem, Coupon, Order, OrderItem

ZERO = Decimal("0.00")
QUOTE_SALT = "orders.checkout-pricing"


@dataclass(frozen=True)
class QuotedLine:
    """One cart line and its calculated purchase amounts."""

    item: CartItem
    subtotal: Decimal
    discount: Decimal

    @property
    def total(self) -> Decimal:
        """Return the amount payable for this line."""
        return self.subtotal - self.discount


@dataclass(frozen=True)
class OrderQuote:
    """A server-calculated preview, also used to write order snapshots."""

    cart: Cart
    lines: tuple[QuotedLine, ...]
    coupon: Coupon | None
    subtotal: Decimal
    discount: Decimal

    @property
    def total(self) -> Decimal:
        """Return the final merchandise total."""
        return self.subtotal - self.discount

    def snapshot(self) -> dict:
        """Return pricing and ownership data; never include payment details."""
        coupon = self.coupon
        return {
            "cart": self.cart.pk,
            "user": self.cart.user_id,
            "coupon": [
                coupon.pk,
                coupon.code,
                coupon.percentage,
                coupon.scope,
                str(coupon.end_date),
                sorted(coupon.products.values_list("pk", flat=True)),
            ]
            if coupon
            else None,
            "lines": [
                [
                    line.item.pk,
                    line.item.product_id,
                    line.item.product.name,
                    line.item.quantity,
                    str(line.item.product.price),
                    str(line.discount),
                ]
                for line in self.lines
            ],
        }

    def signed_snapshot(self) -> str:
        """Sign the displayed prices so a browser cannot change them."""
        return signing.dumps(self.snapshot(), salt=QUOTE_SALT, compress=True)

    def check_snapshot(self, token: str) -> None:
        """Require review when a preview is missing, altered, or out of date."""
        try:
            previous = signing.loads(token, salt=QUOTE_SALT)
        except (signing.BadSignature, TypeError, ValueError):
            previous = None
        if previous != self.snapshot():
            raise ValueError(
                "Checkout pricing needs review. Review the updated totals and place your order again."
            )


def quote_order(cart: Cart, *, coupon_code: str | None = None) -> OrderQuote:
    """Price current cart lines and validate the supplied coupon, if any.

    Raises ValueError for empty/unavailable carts and invalid promotions.
    This operation never changes the cart or creates an order.
    """
    lines = list(cart.lines())
    if not lines:
        raise ValueError("Cannot place an order from an empty cart.")
    unavailable = [line.product.name for line in lines if not line.product.is_available]
    if unavailable:
        raise ValueError(
            f"No longer available: {', '.join(unavailable)}. Remove them from the cart to check out."
        )
    coupon = None
    eligible = set()
    code = Coupon.normalize_code(coupon_code)
    if code:
        coupon = Coupon.objects.filter(code=code).first()
        if coupon is None:
            raise ValueError(
                "That coupon code was not found. Check the code or remove it."
            )
        eligible = coupon.eligible_product_ids(lines)
    quoted = tuple(
        QuotedLine(
            line,
            line.line_total,
            coupon.line_discount(line.line_total)
            if coupon and line.product_id in eligible
            else ZERO,
        )
        for line in lines
    )
    subtotal = sum((line.subtotal for line in quoted), ZERO)
    if subtotal > Decimal("99999999.99"):
        raise ValueError(
            "This cart exceeds the order limit. Reduce quantities to check out."
        )
    return OrderQuote(
        cart, quoted, coupon, subtotal, sum((line.discount for line in quoted), ZERO)
    )


ADDRESS_FIELDS = [
    "email",
    "shipping_name",
    "shipping_street",
    "shipping_line2",
    "shipping_city",
    "shipping_state",
    "shipping_zip",
    "billing_name",
    "billing_street",
    "billing_line2",
    "billing_city",
    "billing_state",
    "billing_zip",
]


@transaction.atomic
def place_order(
    cart: Cart,
    user: AbstractBaseUser,
    checkout_data: Mapping[str, Any],
    *,
    coupon_code: str | None = None,
    expected_snapshot: str | None = None,
) -> Order:
    """Create an order from the cart's contents, then empty the cart.

    ``checkout_data`` is the ``cleaned_data`` of a valid ``CheckoutForm``.
    Addresses and line prices are denormalized onto the order — an order
    is a snapshot, immune to later catalog or address edits. Of the card,
    only the last four digits are stored; the full number and CVV never
    touch the database.

    All-or-nothing: runs in a transaction, so a failure partway through
    leaves no partial order and the cart intact.

    Raises ``ValueError`` for invalid carts/coupons or changed pricing.
    Browser callers must supply the signed preview as ``expected_snapshot``.
    Trusted callers may omit it. No-code callers retain regular checkout.
    """
    if cart.user_id != user.pk:
        raise ValueError("This cart does not belong to you.")
    # Acquire the write lock before reading prices, including on SQLite where
    # select_for_update alone does not lock. Concurrent submissions serialize.
    Cart.objects.filter(pk=cart.pk).update(coupon_code=F("coupon_code"))
    if expected_snapshot is not None:
        cart.refresh_from_db(fields=["coupon_code"])
        if cart.coupon_code != Coupon.normalize_code(coupon_code):
            raise ValueError(
                "Your selected coupon changed. Review the updated totals and place your order again."
            )
    quote = quote_order(cart, coupon_code=coupon_code)
    if expected_snapshot is not None:
        quote.check_snapshot(expected_snapshot)
    card_digits = ""
    if quote.total:
        card_digits = checkout_data["card_number"].replace(" ", "").replace("-", "")
    order = Order.objects.create(
        user=user,
        subtotal=quote.subtotal,
        discount=quote.discount,
        total=quote.total,
        coupon_code=quote.coupon.code if quote.coupon else "",
        coupon_percentage=quote.coupon.percentage if quote.coupon else None,
        card_last4=card_digits[-4:],
        **{name: checkout_data[name] for name in ADDRESS_FIELDS},
    )
    for line in quote.lines:
        OrderItem.objects.create(
            order=order,
            product=line.item.product,
            product_name=line.item.product.name,
            unit_price=line.item.product.price,
            quantity=line.item.quantity,
            discount=line.discount,
        )
    cart.items.all().delete()
    cart.coupon_code = ""
    cart.save(update_fields=["coupon_code"])
    return order
