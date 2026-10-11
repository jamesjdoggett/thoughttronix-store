import pytest


@pytest.fixture
def customer(customer):
    """Existing purchase regressions use a checkout-eligible customer."""
    customer.email = "customer@example.com"
    customer.email_verified = True
    customer.save()
    return customer
