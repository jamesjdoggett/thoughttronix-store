"""The checkout form — the codebase's showcase of declarative validation.

Every rule is visible at its field declaration, in the style of data
annotations: field types validate (``EmailField``), field arguments
validate (``required``, ``max_length``, ``ChoiceField``), and the
``validators=[...]`` list carries the rest. No ``clean_*`` methods
and no ``clean()`` — none of its current rules need imperative validation.
"""

from django import forms
from django.core.validators import RegexValidator
from django.db import transaction

from products.forms import StyledModelForm
from products.models import Product

from .models import Coupon, Order
from .validators import validate_card_number, validate_expiry

US_STATES = [
    ("AL", "Alabama"),
    ("AK", "Alaska"),
    ("AZ", "Arizona"),
    ("AR", "Arkansas"),
    ("CA", "California"),
    ("CO", "Colorado"),
    ("CT", "Connecticut"),
    ("DE", "Delaware"),
    ("DC", "District of Columbia"),
    ("FL", "Florida"),
    ("GA", "Georgia"),
    ("HI", "Hawaii"),
    ("ID", "Idaho"),
    ("IL", "Illinois"),
    ("IN", "Indiana"),
    ("IA", "Iowa"),
    ("KS", "Kansas"),
    ("KY", "Kentucky"),
    ("LA", "Louisiana"),
    ("ME", "Maine"),
    ("MD", "Maryland"),
    ("MA", "Massachusetts"),
    ("MI", "Michigan"),
    ("MN", "Minnesota"),
    ("MS", "Mississippi"),
    ("MO", "Missouri"),
    ("MT", "Montana"),
    ("NE", "Nebraska"),
    ("NV", "Nevada"),
    ("NH", "New Hampshire"),
    ("NJ", "New Jersey"),
    ("NM", "New Mexico"),
    ("NY", "New York"),
    ("NC", "North Carolina"),
    ("ND", "North Dakota"),
    ("OH", "Ohio"),
    ("OK", "Oklahoma"),
    ("OR", "Oregon"),
    ("PA", "Pennsylvania"),
    ("RI", "Rhode Island"),
    ("SC", "South Carolina"),
    ("SD", "South Dakota"),
    ("TN", "Tennessee"),
    ("TX", "Texas"),
    ("UT", "Utah"),
    ("VT", "Vermont"),
    ("VA", "Virginia"),
    ("WA", "Washington"),
    ("WV", "West Virginia"),
    ("WI", "Wisconsin"),
    ("WY", "Wyoming"),
]

zip_validator = RegexValidator(
    r"^\d{5}(-\d{4})?$", "Enter a ZIP code like 79016 or 79016-1234."
)
cvv_validator = RegexValidator(r"^\d{3,4}$", "Enter the 3- or 4-digit CVV.")


class CheckoutForm(forms.Form):
    """One page, one POST: contact, shipping, billing, payment."""

    email = forms.EmailField(label="Email")

    shipping_name = forms.CharField(label="Full name", max_length=100)
    shipping_street = forms.CharField(label="Street address", max_length=200)
    shipping_line2 = forms.CharField(
        label="Apt, suite, etc. (optional)", max_length=200, required=False
    )
    shipping_city = forms.CharField(label="City", max_length=100)
    shipping_state = forms.ChoiceField(label="State", choices=US_STATES)
    shipping_zip = forms.CharField(
        label="ZIP code", max_length=10, validators=[zip_validator]
    )

    billing_name = forms.CharField(label="Full name", max_length=100)
    billing_street = forms.CharField(label="Street address", max_length=200)
    billing_line2 = forms.CharField(
        label="Apt, suite, etc. (optional)", max_length=200, required=False
    )
    billing_city = forms.CharField(label="City", max_length=100)
    billing_state = forms.ChoiceField(label="State", choices=US_STATES)
    billing_zip = forms.CharField(
        label="ZIP code", max_length=10, validators=[zip_validator]
    )

    card_number = forms.CharField(
        label="Card number", max_length=23, validators=[validate_card_number]
    )
    card_expiry = forms.CharField(
        label="Expiry (MM/YY)", max_length=5, validators=[validate_expiry]
    )
    card_cvv = forms.CharField(label="CVV", max_length=4, validators=[cvv_validator])

    def __init__(self, *args, payment_required=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not payment_required:
            for name in ("card_number", "card_expiry", "card_cvv"):
                self.fields.pop(name)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs["class"] = "select w-full"
            else:
                widget.attrs["class"] = "input w-full"

    # Field groups for the template — the form owns its own structure.

    def shipping_fields(self):
        return [self[name] for name in self.fields if name.startswith("shipping_")]

    def billing_fields(self):
        return [self[name] for name in self.fields if name.startswith("billing_")]

    def card_fields(self):
        return [self[name] for name in self.fields if name.startswith("card_")]


class OrderStatusForm(forms.ModelForm):
    """The back-office status dropdown — any of the four states, anytime.

    Guarding the workflow (no un-cancelling, no re-shipping a delivered
    order) is deliberately left as a student exercise.
    """

    class Meta:
        model = Order
        fields = ["status"]
        widgets = {"status": forms.Select(attrs={"class": "select"})}


class CouponCodeForm(forms.Form):
    """Normalize customer input before looking up a promotion."""

    code = forms.CharField(max_length=30)

    def clean_code(self):
        code = Coupon.normalize_code(self.cleaned_data["code"])
        Coupon._meta.get_field("code").run_validators(code)
        return code


class CouponForm(StyledModelForm):
    """Marketing owns promotion terms; the public code stays fixed."""

    class Meta:
        model = Coupon
        fields = ["code", "percentage", "scope", "products", "end_date", "is_active"]
        widgets = {
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "products": forms.CheckboxSelectMultiple,
        }
        help_texts = {
            "products": "Check one or more products for Selected products. Whole order ignores this selection.",
            "is_active": "Activate when ready. Uncheck to retire; existing orders never change.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Each choice is a checkbox, not a DaisyUI single-select or text input.
        self.fields["products"].widget.attrs["class"] = (
            "checkbox checkbox-primary mt-0.5 shrink-0"
        )
        if self.instance.pk:
            self.fields["code"].disabled = True
            self.fields[
                "code"
            ].help_text = (
                "Codes cannot be renamed. Create a new coupon to use a different code."
            )

    def clean_code(self):
        return Coupon.normalize_code(self.cleaned_data["code"])

    def clean(self):
        data = super().clean()
        if data.get("scope") == Coupon.Scope.PRODUCTS and not data.get("products"):
            self.add_error("products", "Select at least one eligible product.")
        return data

    @transaction.atomic
    def save(self, commit=True):
        if self.cleaned_data.get("scope") == Coupon.Scope.ORDER:
            self.cleaned_data["products"] = Product.objects.none()
        return super().save(commit=commit)
