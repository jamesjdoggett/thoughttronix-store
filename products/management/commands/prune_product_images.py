"""Reconcile files left by rolled-back or interrupted image saves."""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from products.models import Product


class Command(BaseCommand):
    help = "List unreferenced product WebPs older than 24 hours; --delete removes them."

    def add_arguments(self, parser) -> None:
        """Default to a reviewable dry run."""
        parser.add_argument("--delete", action="store_true")

    def handle(self, *args, **options) -> None:
        """Preserve referenced and recently staged files while reconciling orphans."""
        storage = Product._meta.get_field("image_catalog").storage
        referenced = {
            name
            for pair in Product.objects.values_list("image_catalog", "image_detail")
            for name in pair
            if name
        }
        if not storage.exists("products"):
            return
        _, filenames = storage.listdir("products")
        cutoff = timezone.now() - timedelta(hours=24)
        for filename in filenames:
            name = f"products/{filename}"
            if (
                not filename.endswith(("-catalog.webp", "-detail.webp"))
                or name in referenced
            ):
                continue
            if storage.get_modified_time(name) >= cutoff:
                continue
            self.stdout.write(f"Unreferenced: {name}")
            if options["delete"]:
                storage.delete(name)
