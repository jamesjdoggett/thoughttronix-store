from django.conf import settings
from django.db import models, transaction

from products.models import Product


class Wishlist(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wishlist"
    )

    def __str__(self):
        return f"Wishlist for {self.user}"

    @classmethod
    def for_user(cls, user):
        wishlist, _ = cls.objects.get_or_create(user=user)
        return wishlist

    def add(self, product):
        """Save once, preserving the original timestamp on repeated requests."""
        with transaction.atomic():
            # Acquire the writer lock before reading on SQLite, and serialize
            # membership changes for this wishlist on row-locking databases.
            type(self).objects.filter(pk=self.pk).update(id=models.F("id"))
            current = Product.objects.select_for_update().get(pk=product.pk)
            existing = self.entries.filter(product=current).first()
            if existing:
                return existing
            if not current.is_available:
                raise ValueError(
                    "This product is no longer available and could not be saved."
                )
            entry, _ = self.entries.get_or_create(product=current)
            return entry

    def remove(self, product):
        self.entries.filter(product=product).delete()


class WishlistEntry(models.Model):
    wishlist = models.ForeignKey(
        Wishlist, on_delete=models.CASCADE, related_name="entries"
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-saved_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["wishlist", "product"], name="unique_wishlist_product"
            )
        ]

    def __str__(self):
        return str(self.product)
