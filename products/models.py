from uuid import uuid4

from django.core.files.base import ContentFile
from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.templatetags.static import static
from django.urls import reverse

# Categories with a dedicated placeholder illustration; anything else
# falls back to default.svg.
PLACEHOLDER_CATEGORIES = {
    "home-assistants",
    "neural-implants",
    "neural-wearables",
    "accessories",
    "defense",
    "legacy-products",
}


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("products:category", kwargs={"slug": self.slug})

    @property
    def placeholder_image(self):
        """Static path of the placeholder image shown for this category's products."""
        if self.slug in PLACEHOLDER_CATEGORIES:
            return f"images/placeholders/{self.slug}.svg"
        return "images/placeholders/default.svg"


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def available(self):
        return self.filter(is_available=True)

    def search(self, text):
        """Simple icontains search over name and description."""
        return self.filter(
            models.Q(name__icontains=text) | models.Q(description__icontains=text)
        )


class Product(models.Model):
    image_catalog = models.FileField(upload_to="products/", blank=True, editable=False)
    image_detail = models.FileField(upload_to="products/", blank=True, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    tagline = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="products")

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs) -> None:
        """Persist image references, cleaning replaced files only after commit."""
        using = kwargs.get("using") or self._state.db or "default"
        old = (
            type(self)
            .objects.using(using)
            .filter(pk=self.pk)
            .values_list("image_catalog", "image_detail")
            .first()
            if self.pk
            else None
        )
        try:
            super().save(*args, **kwargs)
        except Exception:
            for name in getattr(self, "_staged_images", []):
                self.image_catalog.storage.delete(name)
            raise
        current = {self.image_catalog.name, self.image_detail.name}
        if old:
            storage = self.image_catalog.storage
            obsolete = [name for name in old if name and name not in current]
            transaction.on_commit(
                lambda: [storage.delete(name) for name in obsolete], using=using
            )
        self._staged_images = []

    def get_absolute_url(self):
        return reverse("products:detail", kwargs={"slug": self.slug})

    def prepare_image(self, versions: tuple[bytes, bytes]) -> None:
        """Write a complete unique pair; a failed write removes staged files."""
        storage = self.image_catalog.storage
        prefix = f"products/{uuid4().hex}"
        names = []
        attempted = []
        try:
            for label, data in zip(("catalog", "detail"), versions, strict=True):
                name = f"{prefix}-{label}.webp"
                attempted.append(name)
                names.append(storage.save(name, ContentFile(data)))
        except Exception:
            for name in set(names + attempted):
                storage.delete(name)
            raise
        self._staged_images = names
        self.image_catalog, self.image_detail = names

    def _image_url(self, field) -> str:
        try:
            if field.name and field.storage.exists(field.name):
                return field.url
        except OSError:
            pass
        return static(self.category.placeholder_image)

    @property
    def catalog_image_url(self) -> str:
        """Return the small version or the category placeholder if missing."""
        return self._image_url(self.image_catalog)

    @property
    def detail_image_url(self) -> str:
        """Return the detail version or the category placeholder if missing."""
        return self._image_url(self.image_detail)


@receiver(post_delete, sender=Product)
def delete_product_images(sender, instance: Product, using: str, **kwargs) -> None:
    """Remove deleted products' files after the database transaction commits."""
    storage = instance.image_catalog.storage
    names = [
        field.name
        for field in (instance.image_catalog, instance.image_detail)
        if field.name
    ]
    transaction.on_commit(lambda: [storage.delete(name) for name in names], using=using)
