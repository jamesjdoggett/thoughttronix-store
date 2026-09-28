"""Promotion rules, checkout integration, and immutable purchase snapshots."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from dashboard import queries
from products.models import Product

from .forms import CheckoutForm, CouponForm
from .models import Coupon, Order, OrderItem
from .services import place_order, quote_order
from .test_checkout_form import VALID_DATA


def apply_code(client, code, **data):
    return client.post(
        reverse("orders:checkout"), {**data, "action": "apply", "coupon_code": code}
    )


def submit(client, preview, **data):
    return client.post(
        reverse("orders:checkout"),
        {
            **VALID_DATA,
            "coupon_code": preview.context["coupon_input"],
            "pricing_snapshot": preview.context["pricing_snapshot"],
            **data,
        },
    )


def test_mixed_cart_checkout_and_saved_order_match(
    client, customer, mixed_cart, product, coupon
):
    coupon.scope = Coupon.Scope.PRODUCTS
    coupon.save()
    coupon.products.add(product)
    client.force_login(customer)
    preview = apply_code(client, " thoughts50 ", shipping_name="Preserved Name")
    assert preview.status_code == 200
    quote = preview.context["quote"]
    assert (quote.subtotal, quote.discount, quote.total) == (
        Decimal("598.00"),
        Decimal("249.00"),
        Decimal("349.00"),
    )
    assert preview.context["form"]["shipping_name"].value() == "Preserved Name"
    assert not preview.context["form"].errors
    page = preview.content.decode()
    for amount in ("598.00", "249.00", "349.00"):
        assert amount in page
    assert submit(client, preview).status_code == 302
    order = Order.objects.get()
    assert (order.subtotal, order.discount, order.total) == (
        quote.subtotal,
        quote.discount,
        quote.total,
    )
    assert order.coupon_code == "THOUGHTS50"
    assert order.coupon_percentage == 50
    assert order.items.get(product=product).discount == Decimal("249.00")
    accessory = order.items.exclude(product=product).get()
    assert accessory.discount == 0
    assert accessory.net_total == Decimal("100.00")
    mixed_cart.refresh_from_db()
    assert mixed_cart.coupon_code == ""
    assert not mixed_cart.items.exists()
    assert queries.total_revenue() == Decimal("349.00")
    assert sum(row["revenue"] for row in queries.top_products()) == Decimal("349.00")
    assert queries.top_products()[0]["revenue"] == Decimal("249.00")
    for name in ("orders:confirmation", "orders:detail"):
        page = client.get(reverse(name, args=[order.pk])).content.decode()
        for text in ("THOUGHTS50", "598.00", "249.00", "349.00"):
            assert text in page


def test_order_wide_discount_includes_every_line(mixed_cart, coupon):
    quote = quote_order(mixed_cart, coupon_code=coupon.code)
    assert (quote.subtotal, quote.discount, quote.total) == (
        Decimal("598.00"),
        Decimal("299.00"),
        Decimal("299.00"),
    )
    assert [line.discount for line in quote.lines] == [
        Decimal("249.00"),
        Decimal("50.00"),
    ]


def test_rounding_is_per_line_half_up(mixed_cart, coupon):
    Product.objects.update(price=Decimal("0.05"))
    mixed_cart.items.update(quantity=1)
    quote = quote_order(mixed_cart, coupon_code=coupon.code)
    assert quote.subtotal == Decimal("0.10")
    assert quote.discount == Decimal("0.06")
    assert quote.total == Decimal("0.04")


@pytest.mark.parametrize(
    "state,message",
    [
        ("expired", "expired"),
        ("inactive", "inactive"),
        ("unknown", "not found"),
        ("ineligible", "does not apply"),
    ],
)
def test_invalid_coupons_block_orders_with_readable_message(
    client, customer, cart, cart_item, coupon, state, message
):
    if state == "expired":
        coupon.end_date = date(2000, 1, 1)
    if state == "inactive":
        coupon.is_active = False
    if state == "ineligible":
        coupon.scope = Coupon.Scope.PRODUCTS
    coupon.save()
    client.force_login(customer)
    preview = apply_code(client, "UNKNOWN" if state == "unknown" else coupon.code)
    assert message in preview.content.decode()
    response = submit(client, preview)
    assert response.status_code == 200
    assert message in response.content.decode()
    assert not Order.objects.exists()
    assert cart.items.exists()
    assert "12 Cortex Lane" in response.content.decode()


@pytest.mark.parametrize(
    "end,instant,expired",
    [
        (date(2026, 7, 1), "2026-07-02T04:59:59+00:00", False),
        (date(2026, 7, 1), "2026-07-02T05:00:00+00:00", True),
        (date(2026, 1, 1), "2026-01-02T05:59:59+00:00", False),
        (date(2026, 1, 1), "2026-01-02T06:00:00+00:00", True),
        (date(2026, 3, 8), "2026-03-09T04:59:59+00:00", False),
        (date(2026, 3, 8), "2026-03-09T05:00:00+00:00", True),
        (date(2026, 11, 1), "2026-11-02T05:59:59+00:00", False),
        (date(2026, 11, 1), "2026-11-02T06:00:00+00:00", True),
    ],
)
def test_expiration_uses_central_midnight(coupon, monkeypatch, end, instant, expired):
    coupon.end_date = end
    monkeypatch.setattr(
        "orders.models.timezone.now", lambda: datetime.fromisoformat(instant)
    )
    assert coupon.is_expired is expired


def test_retirement_and_edits_do_not_rewrite_orders(cart, cart_item, coupon, product):
    order = place_order(cart, cart.user, VALID_DATA, coupon_code=coupon.code)
    coupon.is_active = False
    coupon.percentage = 10
    coupon.scope = Coupon.Scope.PRODUCTS
    coupon.save()
    coupon.products.clear()
    product.price = Decimal("900.00")
    product.save()
    order.refresh_from_db()
    assert (order.subtotal, order.discount, order.total) == (
        Decimal("699.98"),
        Decimal("349.99"),
        Decimal("349.99"),
    )
    assert order.coupon_percentage == 50
    assert order.coupon_code == "THOUGHTS50"
    assert order.items.get().discount == Decimal("349.99")
    product.delete()
    assert order.items.get().net_total == Decimal("349.99")


def test_reusable_after_success_and_reactivation(cart, cart_item, coupon, product):
    place_order(cart, cart.user, VALID_DATA, coupon_code=coupon.code)
    cart.add(product)
    coupon.is_active = False
    coupon.save()
    with pytest.raises(ValueError, match="inactive"):
        place_order(cart, cart.user, VALID_DATA, coupon_code=coupon.code)
    coupon.is_active = True
    coupon.save()
    place_order(cart, cart.user, VALID_DATA, coupon_code=coupon.code)
    assert Order.objects.count() == 2


def test_free_order_ignores_card_fields_and_displays_no_payment(
    client, customer, cart_item, coupon
):
    coupon.percentage = 100
    coupon.save()
    client.force_login(customer)
    preview = apply_code(client, coupon.code)
    assert "No payment required" in preview.content.decode()
    assert 'name="card_number"' not in preview.content.decode()
    assert (
        submit(client, preview, card_number="", card_cvv="", card_expiry="").status_code
        == 302
    )
    order = Order.objects.get()
    assert order.total == 0
    assert order.card_last4 == ""
    for route in ("orders:confirmation", "orders:detail"):
        page = client.get(reverse(route, args=[order.pk])).content.decode()
        assert "No payment required" in page
        assert "card ending" not in page


def test_removing_free_coupon_restores_card_validation(
    client, customer, cart_item, coupon
):
    coupon.percentage = 100
    coupon.save()
    client.force_login(customer)
    apply_code(client, coupon.code)
    preview = client.post(reverse("orders:checkout"), {"action": "remove"})
    assert 'name="card_number"' in preview.content.decode()
    response = submit(client, preview, card_number="")
    assert "card_number" in response.context["form"].errors
    assert not Order.objects.exists()


def test_free_orders_still_require_contact_and_addresses():
    form = CheckoutForm({}, payment_required=False)
    assert not form.is_valid()
    assert "email" in form.errors and "billing_street" in form.errors
    assert "card_number" not in form.fields


@pytest.mark.parametrize(
    "change",
    [
        "price",
        "quantity",
        "percentage",
        "scope",
        "end_date",
        "inactive",
        "expired",
        "remove_eligible",
    ],
)
def test_changes_between_preview_and_submit_require_review(
    client, customer, mixed_cart, product, coupon, change
):
    coupon.scope = Coupon.Scope.PRODUCTS
    coupon.save()
    coupon.products.add(product)
    client.force_login(customer)
    preview = apply_code(client, coupon.code)
    if change == "price":
        product.price += 10
        product.save()
    elif change == "quantity":
        mixed_cart.items.filter(product=product).update(quantity=3)
    elif change == "remove_eligible":
        coupon.products.clear()
    else:
        if change == "percentage":
            coupon.percentage = 25
        elif change == "scope":
            coupon.scope = Coupon.Scope.ORDER
        elif change == "end_date":
            coupon.end_date += timedelta(days=1)
        elif change == "inactive":
            coupon.is_active = False
        elif change == "expired":
            coupon.end_date = date(2000, 1, 1)
        coupon.save()
    response = submit(client, preview)
    assert response.status_code == 200
    assert not Order.objects.exists()
    assert mixed_cart.items.exists()
    if change not in {"inactive", "expired", "remove_eligible"}:
        assert "Review the updated totals" in response.content.decode()
        assert submit(client, response).status_code == 302


def test_selected_code_persists_and_recalculates_on_return(
    client, customer, cart, cart_item, coupon
):
    client.force_login(customer)
    apply_code(client, coupon.code)
    cart_item.increment()
    preview = client.get(reverse("orders:checkout"))
    assert preview.context["coupon_input"] == coupon.code
    assert preview.context["quote"].discount == Decimal("524.99")
    removed = client.post(
        reverse("orders:checkout"), {"action": "remove", "shipping_name": "Remember Me"}
    )
    assert removed.context["quote"].discount == 0
    assert removed.context["form"]["shipping_name"].value() == "Remember Me"
    cart.refresh_from_db()
    assert cart.coupon_code == ""


def test_htmx_apply_returns_partial_without_validating_addresses(
    client, customer, cart_item, coupon
):
    client.force_login(customer)
    response = client.post(
        reverse("orders:checkout"),
        {"action": "apply", "coupon_code": coupon.code, "shipping_name": "Keep Me"},
        HTTP_HX_REQUEST="true",
    )
    page = response.content.decode()
    assert response.status_code == 200
    assert '<div id="checkout-panel"' in page
    assert "<html" not in page
    assert "Keep Me" in page
    assert "This field is required" not in page


@pytest.mark.parametrize("token", ["", "forged"])
def test_missing_or_tampered_preview_cannot_place_order(
    client, customer, cart_item, token
):
    client.force_login(customer)
    response = client.post(
        reverse("orders:checkout"), {**VALID_DATA, "pricing_snapshot": token}
    )
    assert response.status_code == 200
    assert "Review the updated totals" in response.content.decode()
    assert not Order.objects.exists()


def test_unapplied_code_is_not_silently_ignored(client, customer, cart_item, coupon):
    client.force_login(customer)
    preview = client.get(reverse("orders:checkout"))
    response = submit(client, preview, coupon_code=coupon.code)
    assert "Apply your entered coupon" in response.content.decode()
    assert not Order.objects.exists()


def test_discount_and_code_roll_back_on_line_failure(mixed_cart, coupon, monkeypatch):
    mixed_cart.coupon_code = coupon.code
    mixed_cart.save()
    original = OrderItem.objects.create
    calls = []

    def fail_on_second(**kwargs):
        calls.append(kwargs)
        if len(calls) == 2:
            raise RuntimeError("line failure")
        return original(**kwargs)

    monkeypatch.setattr(OrderItem.objects, "create", fail_on_second)
    with pytest.raises(RuntimeError):
        place_order(mixed_cart, mixed_cart.user, VALID_DATA, coupon_code=coupon.code)
    mixed_cart.refresh_from_db()
    assert mixed_cart.coupon_code == coupon.code
    assert mixed_cart.items.count() == 2
    assert not Order.objects.exists()
    assert not OrderItem.objects.exists()


@pytest.mark.parametrize("percentage", [0, 101, -1, "12.5"])
def test_staff_form_rejects_invalid_percentage(db, percentage):
    form = CouponForm(
        {
            "code": "WINTER",
            "percentage": percentage,
            "scope": "ORDER",
            "end_date": "2030-12-31",
        }
    )
    assert not form.is_valid()
    assert "percentage" in form.errors


@pytest.mark.parametrize("code", ["AB", "A" * 31, "HAS SPACE", "50%OFF", "ÉTÉ"])
def test_staff_form_rejects_invalid_codes(db, code):
    form = CouponForm(
        {"code": code, "percentage": 50, "scope": "ORDER", "end_date": "2030-12-31"}
    )
    assert not form.is_valid()
    assert "code" in form.errors


def test_codes_are_normalized_unique_and_fixed(coupon):
    form = CouponForm(
        {
            "code": " thoughts50 ",
            "percentage": 25,
            "scope": "ORDER",
            "end_date": "2030-12-31",
        }
    )
    assert not form.is_valid()
    assert "code" in form.errors
    coupon.code = "RENAMED"
    with pytest.raises(ValidationError, match="cannot be renamed"):
        coupon.save()


def test_product_selection_required_and_cleared_for_order_scope(db, product):
    data = {
        "code": "NEW50",
        "percentage": 50,
        "scope": "PRODUCTS",
        "end_date": "2030-12-31",
    }
    form = CouponForm(data)
    assert not form.is_valid()
    assert "products" in form.errors
    form = CouponForm({**data, "products": [product.pk]})
    assert form.is_valid(), form.errors
    coupon = form.save()
    assert list(coupon.products.all()) == [product]
    assert not coupon.is_active
    form = CouponForm(
        {**data, "scope": "ORDER", "products": [product.pk]}, instance=coupon
    )
    assert form.is_valid(), form.errors
    form.save()
    assert not coupon.products.exists()


def test_staff_can_create_edit_retire_and_reactivate(client, staff_user, product):
    client.force_login(staff_user)
    assert (
        "No coupons yet"
        in client.get(reverse("orders:manage_coupons")).content.decode()
    )
    data = {
        "code": " spring-50 ",
        "percentage": 50,
        "scope": "PRODUCTS",
        "products": [product.pk],
        "end_date": "2030-12-31",
        "is_active": "on",
    }
    assert client.post(reverse("orders:create_coupon"), data).status_code == 302
    coupon = Coupon.objects.get()
    assert coupon.code == "SPRING-50"
    assert coupon.is_active
    data.pop("is_active")
    data["code"] = "ATTEMPTED-RENAME"
    assert (
        client.post(reverse("orders:edit_coupon", args=[coupon.pk]), data).status_code
        == 302
    )
    coupon.refresh_from_db()
    assert not coupon.is_active
    assert coupon.code == "SPRING-50"
    assert (
        client.post(
            reverse("orders:edit_coupon", args=[coupon.pk]), {**data, "is_active": "on"}
        ).status_code
        == 302
    )
    coupon.refresh_from_db()
    assert coupon.is_active


def test_coupon_management_requires_staff(client, customer, coupon):
    paths = [
        reverse("orders:manage_coupons"),
        reverse("orders:create_coupon"),
        reverse("orders:edit_coupon", args=[coupon.pk]),
    ]
    for path in paths:
        assert client.get(path).status_code == 302
    client.force_login(customer)
    for path in paths:
        assert client.get(path).status_code == 403
        assert client.post(path, {}).status_code == 403


def test_service_rechecks_coupon_after_view_validation(
    client, customer, cart_item, coupon, monkeypatch
):
    client.force_login(customer)
    preview = apply_code(client, coupon.code)
    original = place_order

    def retire_then_place(*args, **kwargs):
        Coupon.objects.filter(pk=coupon.pk).update(is_active=False)
        return original(*args, **kwargs)

    monkeypatch.setattr("orders.views.place_order", retire_then_place)
    response = submit(client, preview)
    assert response.status_code == 200
    assert "inactive" in response.content.decode()
    assert not Order.objects.exists()


def test_service_rechecks_selected_code_from_another_tab(cart, cart_item, coupon):
    cart.coupon_code = coupon.code
    cart.save()
    token = quote_order(cart, coupon_code=coupon.code).signed_snapshot()
    type(cart).objects.filter(pk=cart.pk).update(coupon_code="")
    with pytest.raises(ValueError, match="selected coupon changed"):
        place_order(
            cart,
            cart.user,
            VALID_DATA,
            coupon_code=coupon.code,
            expected_snapshot=token,
        )
    assert not Order.objects.exists()
    assert cart.items.exists()


def test_duplicate_checkout_submission_creates_one_order(
    client, customer, cart_item, coupon
):
    client.force_login(customer)
    preview = apply_code(client, coupon.code)
    assert submit(client, preview).status_code == 302
    response = submit(client, preview)
    assert response.status_code == 302
    assert response.url == reverse("orders:cart")
    assert Order.objects.count() == 1


def test_coupon_failure_preserves_existing_order_access_rules(
    client, customer, cart, cart_item, coupon, staff_user
):
    order = place_order(cart, customer, VALID_DATA, coupon_code=coupon.code)
    client.force_login(staff_user)
    for name in ("orders:detail", "orders:confirmation"):
        assert client.get(reverse(name, args=[order.pk])).status_code == 404
    page = client.get(
        reverse("orders:manage_order_detail", args=[order.pk])
    ).content.decode()
    assert coupon.code in page
    assert "349.99" in page


def test_net_revenue_still_excludes_cancelled_orders(cart, cart_item, coupon):
    order = place_order(cart, cart.user, VALID_DATA, coupon_code=coupon.code)
    order.status = Order.Status.CANCELLED
    order.save()
    assert queries.total_revenue() == 0
    assert queries.top_products() == []
