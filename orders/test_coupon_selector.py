"""Staff can read, select, and retain multiple coupon products."""

from html.parser import HTMLParser

from django.urls import reverse

from .models import Coupon


class ProductInputs(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.inputs = {}
        self.label_targets = []
        self.feed(content.decode())

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("name") == "products":
            self.inputs[attrs["value"]] = attrs
        if tag == "label" and "for" in attrs:
            self.label_targets.append(attrs["for"])


def test_new_coupon_has_individually_labelled_product_checkboxes(
    client, staff_user, product, unavailable_product
):
    client.force_login(staff_user)
    response = client.get(reverse("orders:create_coupon"))
    parsed = ProductInputs(response.content)
    assert set(parsed.inputs) == {str(product.pk), str(unavailable_product.pk)}
    assert len({attrs["id"] for attrs in parsed.inputs.values()}) == 2
    for attrs in parsed.inputs.values():
        assert attrs["type"] == "checkbox"
        assert attrs["id"] in parsed.label_targets
        assert "checked" not in attrs
    assert product.name in response.content.decode()
    assert unavailable_product.name in response.content.decode()


def test_multiple_selections_save_and_survive_invalid_edit(
    client, staff_user, product, unavailable_product
):
    client.force_login(staff_user)
    data = {
        "code": "PICK-TWO",
        "percentage": 50,
        "scope": "PRODUCTS",
        "products": [product.pk, unavailable_product.pk],
        "end_date": "2030-12-31",
    }
    response = client.post(reverse("orders:create_coupon"), data)
    assert response.status_code == 302
    coupon = Coupon.objects.get(code="PICK-TWO")
    assert set(coupon.products.values_list("pk", flat=True)) == {
        product.pk, unavailable_product.pk,
    }
    edit_url = reverse("orders:edit_coupon", args=[coupon.pk])
    parsed = ProductInputs(client.get(edit_url).content)
    assert all("checked" in attrs for attrs in parsed.inputs.values())

    # A validation error must retain the staff member's changed selection.
    response = client.post(edit_url, {**data, "percentage": 101, "products": [product.pk]})
    assert response.status_code == 200
    assert "percentage" in response.context["form"].errors
    parsed = ProductInputs(response.content)
    assert "checked" in parsed.inputs[str(product.pk)]
    assert "checked" not in parsed.inputs[str(unavailable_product.pk)]
    assert coupon.products.count() == 2

    assert client.post(edit_url, {**data, "products": [product.pk]}).status_code == 302
    assert list(coupon.products.values_list("pk", flat=True)) == [product.pk]


def test_empty_selection_shows_error_beside_product_picker(client, staff_user, product):
    client.force_login(staff_user)
    response = client.post(reverse("orders:create_coupon"), {
        "code": "EMPTY", "percentage": 50, "scope": "PRODUCTS", "end_date": "2030-12-31",
    })
    assert response.status_code == 200
    assert "Select at least one eligible product." in response.content.decode()
    assert 'id="id_products_errors"' in response.content.decode()
    assert not Coupon.objects.exists()


def test_empty_catalog_explains_how_to_add_eligible_products(client, staff_user):
    client.force_login(staff_user)
    response = client.get(reverse("orders:create_coupon"))
    assert "No products available. Add a product" in response.content.decode()
    assert not ProductInputs(response.content).inputs
