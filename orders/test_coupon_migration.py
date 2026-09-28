"""Existing purchases keep their amounts when coupon snapshots are introduced."""

from decimal import Decimal

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_existing_orders_gain_undiscounted_snapshots():
    old_target = [("orders", "0002_order_orderitem")]
    new_target = [("orders", "0003_cart_coupon_code_order_coupon_code_and_more")]
    executor = MigrationExecutor(connection)
    executor.migrate(old_target)
    try:
        apps = executor.loader.project_state(old_target).apps
        user = apps.get_model("accounts", "User").objects.create(username="legacy")
        order = apps.get_model("orders", "Order").objects.create(
            user=user,
            total=Decimal("699.98"),
            card_last4="4242",
        )
        apps.get_model("orders", "OrderItem").objects.create(
            order=order,
            product_name="Historical Seraphine",
            unit_price=Decimal("349.99"),
            quantity=2,
        )
        executor = MigrationExecutor(connection)
        executor.migrate(new_target)
        apps = executor.loader.project_state(new_target).apps
        saved = apps.get_model("orders", "Order").objects.get(pk=order.pk)
        line = apps.get_model("orders", "OrderItem").objects.get(order_id=order.pk)
        assert saved.subtotal == saved.total == Decimal("699.98")
        assert saved.discount == line.discount == 0
        assert saved.coupon_code == ""
        assert saved.coupon_percentage is None
        assert saved.card_last4 == "4242"
        assert line.unit_price == Decimal("349.99")
    finally:
        MigrationExecutor(connection).migrate(new_target)
