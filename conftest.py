"""Project-wide pytest fixtures.

Shared test data lives here as plain fixtures — no factories. The suite
grows with the project; tests never invoke the seed command.
"""

from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from orders.models import Cart, CartItem, Coupon
from products.models import Category, Product, Tag


@pytest.fixture
def customer(db):
    return get_user_model().objects.create_user(
        username="customer", password="customer123"
    )


@pytest.fixture
def staff_user(db):
    return get_user_model().objects.create_user(
        username="employee",
        password="employee123",
        is_staff=True,
        job_title="Junior Thought Curator",
    )


@pytest.fixture
def category(db):
    return Category.objects.create(name="Home Assistants", slug="home-assistants")


@pytest.fixture
def product(category):
    return Product.objects.create(
        name="Seraphine Home Hub",
        slug="seraphine-home-hub",
        tagline="She's always listening. In a good way.",
        description="The flagship Seraphine hub with a seven-microphone array.",
        price=Decimal("349.99"),
        category=category,
    )


@pytest.fixture
def unavailable_product(category):
    return Product.objects.create(
        name="EchoPatch",
        slug="echopatch",
        tagline="Never miss a word. Anyone's.",
        price=Decimal("139.00"),
        is_available=False,
        category=category,
    )


@pytest.fixture
def tag(db):
    return Tag.objects.create(name="bestseller", slug="bestseller")


@pytest.fixture
def cart(customer):
    return Cart.for_user(customer)


@pytest.fixture
def cart_item(cart, product):
    return CartItem.objects.create(cart=cart, product=product, quantity=2)


@pytest.fixture
def coupon(db):
    return Coupon.objects.create(
        code="THOUGHTS50",
        percentage=50,
        is_active=True,
        end_date=timezone.localdate(timezone=ZoneInfo("America/Chicago"))
        + timedelta(days=30),
    )


@pytest.fixture
def mixed_cart(cart, cart_item, product, category):
    product.price = Decimal("249.00")
    product.save()
    accessory = Product.objects.create(
        name="Accessory",
        slug="accessory",
        price=Decimal("100.00"),
        category=category,
    )
    cart.add(accessory)
    return cart
