"""Legacy email cleanup preserves accounts and purchase relationships."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from orders.models import Cart, Order


@pytest.mark.django_db(transaction=True)
def test_legacy_email_migration():
    executor = MigrationExecutor(connection)
    leaves = executor.loader.graph.leaf_nodes()
    old = [("accounts", "0001_initial")]
    executor.migrate(old)
    try:
        apps = executor.loader.project_state(old).apps
        User = apps.get_model("accounts", "User")
        records = [
            User.objects.create(
                username="one", email=" Same@Example.com ", is_staff=True
            ),
            User.objects.create(
                username="two", email="same@example.com", is_superuser=True
            ),
            User.objects.create(username="invalid", email="bad email"),
            User.objects.create(username="missing", email=""),
            User.objects.create(username="valid", email=" Good+tag@Example.com "),
        ]
        cart = Cart.objects.create(user_id=records[0].pk)
        order = Order.objects.create(
            user_id=records[0].pk,
            total="12.00",
            card_last4="4242",
            email="Snapshot@Example.com",
        )
        # Restore all apps so relationship models can be inspected together.
        executor = MigrationExecutor(connection)
        executor.migrate(leaves)
        apps = executor.loader.project_state(leaves).apps
        User = apps.get_model("accounts", "User")
        assert Cart.objects.get(pk=cart.pk).user_id == records[0].pk
        saved_order = Order.objects.get(pk=order.pk)
        assert saved_order.user_id == records[0].pk
        assert saved_order.email == "Snapshot@Example.com"
        assert saved_order.total == 12
        for original in records:
            saved = User.objects.get(pk=original.pk)
            assert saved.username == original.username
            assert saved.is_staff == original.is_staff
            assert saved.is_superuser == original.is_superuser
            assert not saved.email_verified
            if original.username == "valid":
                assert saved.email == "good+tag@example.com"
            else:
                assert saved.email == ""
                assert saved.legacy_email == original.email
    finally:
        MigrationExecutor(connection).migrate(leaves)
