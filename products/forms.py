"""Back-office forms for the catalog models.

ModelForms inherit the models' own rules (name required, slug unique);
the explicit ``price`` declaration adds the one rule the model doesn't
carry — the price must be positive. Widgets get their DaisyUI classes
in one shared ``__init__`` loop, as on ``CheckoutForm``.
"""

from decimal import Decimal

from django import forms
from django.core.files.uploadedfile import UploadedFile

from .images import IMAGE_HELP, optimize_image
from .models import Category, Product, Tag


class StyledModelForm(forms.ModelForm):
    """Base form that dresses every widget in DaisyUI classes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "toggle toggle-primary"
            elif isinstance(widget, forms.Textarea):
                widget.attrs["class"] = "textarea w-full"
                widget.attrs.setdefault("rows", 6)
            elif isinstance(widget, forms.SelectMultiple):
                widget.attrs["class"] = "select h-auto w-full"
                widget.attrs.setdefault("size", 8)
            elif isinstance(widget, forms.Select):
                widget.attrs["class"] = "select w-full"
            elif isinstance(widget, forms.FileInput):
                widget.attrs["class"] = "file-input w-full"
            else:
                widget.attrs["class"] = "input w-full"


class ProductForm(StyledModelForm):
    image = forms.FileField(
        required=False,
        help_text=IMAGE_HELP,
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )
    remove_image = forms.BooleanField(
        required=False, help_text="Restore the category placeholder."
    )

    def clean_image(self) -> UploadedFile | None:
        """Validate and encode in memory; never persist an invalid form's upload."""
        upload = self.cleaned_data.get("image")
        self._image_versions = optimize_image(upload) if upload else None
        return upload

    def clean(self) -> dict:
        """Require an unambiguous replacement or removal."""
        data = super().clean()
        if data.get("image") and data.get("remove_image"):
            self.add_error("image", "Choose either a replacement image or removal.")
        return data

    def _post_clean(self):
        super()._post_clean()
        if self.errors:
            return
        if self.cleaned_data.get("remove_image"):
            self.instance.image_catalog = ""
            self.instance.image_detail = ""
        elif getattr(self, "_image_versions", None):
            try:
                self.instance.prepare_image(self._image_versions)
            except OSError:
                self.add_error(
                    "image",
                    "The image could not be stored. Please try again; your previous image is unchanged.",
                )

    price = forms.DecimalField(
        label="Price (USD)",
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )

    class Meta:
        model = Product
        fields = [
            "name",
            "slug",
            "tagline",
            "description",
            "price",
            "category",
            "tags",
            "is_available",
            "image",
            "remove_image",
        ]


class CategoryForm(StyledModelForm):
    class Meta:
        model = Category
        fields = ["name", "slug"]


class TagForm(StyledModelForm):
    class Meta:
        model = Tag
        fields = ["name", "slug"]
