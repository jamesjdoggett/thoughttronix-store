from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models.functions import Upper
from django.utils import timezone

from products.models import Product


class Coupon(models.Model):
    """A reusable promotion; orders store their own purchase-time snapshots."""

    class Scope(models.TextChoices):
        ORDER = "ORDER", "Whole order"
        PRODUCTS = "PRODUCTS", "Selected products"

    code = models.CharField(
        max_length=30,
        unique=True,
        validators=[
            RegexValidator(
                r"\A[A-Z0-9-]{3,30}\Z", "Use 3–30 letters, digits, or hyphens."
            )
        ],
    )
    percentage = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    scope = models.CharField(max_length=8, choices=Scope.choices, default=Scope.ORDER)
    products = models.ManyToManyField(Product, blank=True, related_name="coupons")
    end_date = models.DateField(
        help_text="Valid through this date in America/Chicago (Central time)."
    )
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(Upper("code"), name="coupon_code_case_unique"),
            models.CheckConstraint(
                condition=models.Q(percentage__gte=1, percentage__lte=100),
                name="coupon_percentage_range",
            ),
            models.CheckConstraint(
                condition=models.Q(scope__in=["ORDER", "PRODUCTS"]),
                name="coupon_valid_scope",
            ),
        ]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.normalize_code(self.code)
        self.full_clean()
        return super().save(*args, **kwargs)

    @staticmethod
    def normalize_code(code):
        return (code or "").strip().upper()

    def clean(self):
        super().clean()
        if self.pk:
            original = (
                type(self)
                .objects.filter(pk=self.pk)
                .values_list("code", flat=True)
                .first()
            )
            if original is not None and self.code != original:
                raise ValidationError({"code": "A coupon code cannot be renamed."})

    @property
    def is_expired(self):
        return timezone.localdate(timezone=ZoneInfo("America/Chicago")) > self.end_date

    @property
    def status(self):
        if not self.is_active:
            return "Inactive"
        return "Expired" if self.is_expired else "Active"

    def eligible_product_ids(self, lines):
        """Validate current eligibility; never widen an empty product selection."""
        if self.is_expired:
            raise ValueError(
                "This coupon has expired. Remove it or enter another code."
            )
        if not self.is_active:
            raise ValueError(
                "This coupon is inactive. Remove it or enter another code."
            )
        eligible = {line.product_id for line in lines}
        if self.scope == self.Scope.PRODUCTS:
            eligible &= set(self.products.values_list("pk", flat=True))
        if not eligible:
            raise ValueError(
                "This coupon does not apply to any products in your cart. Remove it or add an eligible product."
            )
        return eligible

    def line_discount(self, subtotal):
        return (subtotal * Decimal(self.percentage) / 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )


class Cart(models.Model):
    """A customer's cart — one per user, created lazily on first touch."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
    )
    coupon_code = models.CharField(max_length=30, blank=True, default="")

    def __str__(self):
        return f"Cart for {self.user.username}"

    @classmethod
    def for_user(cls, user):
        """Return the user's cart, creating it on first touch."""
        cart, _ = cls.objects.get_or_create(user=user)
        return cart

    def add(self, product):
        """Add a product to the cart; a duplicate add increments its line."""
        item, created = self.items.get_or_create(product=product)
        if not created:
            item.quantity += 1
            item.save()
        return item

    def lines(self):
        """Line items with their products loaded, ready for display."""
        return self.items.select_related("product")

    def total(self):
        return sum((item.line_total for item in self.lines()), Decimal("0.00"))

    def item_count(self):
        """Total units across all lines — the navbar badge number."""
        return self.items.aggregate(count=models.Sum("quantity"))["count"] or 0


class CartItem(models.Model):
    """One product line in a cart; the cart–product pair is unique."""

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "product"], name="unique_cart_product"
            )
        ]

    def __str__(self):
        return f"{self.quantity} × {self.product.name}"

    @property
    def line_total(self):
        return self.product.price * self.quantity

    def increment(self):
        self.quantity += 1
        self.save()

    def decrement(self):
        """Step the quantity down, stopping at one — removal is explicit."""
        if self.quantity > 1:
            self.quantity -= 1
            self.save()


class Order(models.Model):
    """A placed order — a snapshot, never a live view of the catalog.

    Addresses are flat denormalized fields: the order must not change if
    the customer later edits anything. Of the card, only the last four
    digits survive checkout.
    """

    class Status(models.TextChoices):
        PLACED = "PLACED", "Placed"
        SHIPPED = "SHIPPED", "Shipped"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PLACED
    )
    total = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    coupon_code = models.CharField(max_length=30, blank=True, default="")
    coupon_percentage = models.PositiveSmallIntegerField(null=True, blank=True)
    email = models.EmailField()

    shipping_name = models.CharField(max_length=100)
    shipping_street = models.CharField(max_length=200)
    shipping_line2 = models.CharField(max_length=200, blank=True)
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=2)
    shipping_zip = models.CharField(max_length=10)

    billing_name = models.CharField(max_length=100)
    billing_street = models.CharField(max_length=200)
    billing_line2 = models.CharField(max_length=200, blank=True)
    billing_city = models.CharField(max_length=100)
    billing_state = models.CharField(max_length=2)
    billing_zip = models.CharField(max_length=10)

    card_last4 = models.CharField(max_length=4, blank=True)

    # default (not auto_now_add) so the seed can backdate orders.
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.number

    @property
    def number(self):
        """The customer-facing order number, e.g. ``TT-2026-00042``."""
        return f"TT-{self.created_at.year}-{self.pk:05d}"


class OrderItem(models.Model):
    """One line of an order, priced as of purchase time.

    Name and unit price are denormalized: order history must not change
    when the catalog does. The product FK survives for linking while the
    product exists.
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_name = models.CharField(max_length=200)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return f"{self.quantity} × {self.product_name}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    @property
    def net_total(self):
        return self.line_total - self.discount
