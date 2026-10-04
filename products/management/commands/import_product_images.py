"""Import the explicitly selected marketing artwork without changing sources."""

from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

from products.images import optimize_image
from products.models import Product

ARTWORK = {
    "Calm Collar GPT Man.png": "calm-collar",
    "CrowdCalm Array No Text.png": "crowdcalm-array",
    "DreamWeaver Matrix GPT 3.png": "dreamweaver",
    "Hush GPT No Text.png": "hush",
    "MindSync Duo.png": "mindsync-duo",
    "MindSync GPT 2.png": "mindsync",
    "MoodSet GPT No Text.png": "moodset",
    "RecallPro.png": "recallpro",
    "Seraphine GPT Text.png": "seraphine",
    "SoulSear No Text.png": "soulsear-mark-i",
    "SyncRest GPT No Text.png": "syncrest",
    "Veil GPT Text.png": "veil",
}


class Command(BaseCommand):
    help = "Import selected marketing images into products without existing images."

    def add_arguments(self, parser) -> None:
        """Allow a separate read-only source directory."""
        parser.add_argument(
            "--source", type=Path, default=settings.BASE_DIR / "product-images"
        )

    def handle(self, *args, **options) -> None:
        """Report each assignment, skip or failure and continue the batch."""
        imported = skipped = failed = 0
        for filename, slug in ARTWORK.items():
            try:
                with transaction.atomic():
                    product = Product.objects.select_for_update().get(slug=slug)
                    if product.image_catalog or product.image_detail:
                        self.stdout.write(f"Skipped {slug}: already has an image.")
                        skipped += 1
                        continue
                    with (options["source"] / filename).open("rb") as source:
                        versions = optimize_image(File(source))
                    product.prepare_image(versions)
                    product.save()
                self.stdout.write(f"Imported {filename} -> {slug}")
                imported += 1
            except Product.DoesNotExist:
                self.stderr.write(f"Missing target product: {slug}")
                failed += 1
            except (OSError, ValidationError) as exc:
                self.stderr.write(f"Failed {slug} ({filename}): {exc}")
                failed += 1
        self.stdout.write(
            f"Imported: {imported}; skipped: {skipped}; failed: {failed}."
        )
