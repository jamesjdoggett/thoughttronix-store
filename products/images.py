"""Small image validation and encoding helpers shared by catalog forms/imports."""

import warnings
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files import File
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 20_000_000
IMAGE_HELP = "Still JPEG, PNG or WebP; at most 10 MiB, 20 million pixels, and at least 400 × 400 pixels."


def optimize_image(upload: File) -> tuple[bytes, bytes]:
    """Fully decode artwork and return catalog/detail WebP bytes without enlarging."""
    if upload.size > MAX_BYTES:
        raise ValidationError("Choose an image no larger than 10 MiB.")
    upload.seek(0)
    data = upload.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValidationError("Choose an image no larger than 10 MiB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValidationError("Choose a still JPEG, PNG or WebP image.")
                if getattr(image, "n_frames", 1) != 1:
                    raise ValidationError(
                        "Animated images are not supported. Choose a still image."
                    )
                width, height = image.size
                if width * height > MAX_PIXELS:
                    raise ValidationError(
                        "Choose an image with at most 20 million pixels."
                    )
                if width < 400 or height < 400:
                    raise ValidationError(
                        "Choose an image at least 400 pixels wide and 400 pixels tall."
                    )
                image.verify()
            with Image.open(BytesIO(data)) as image:
                image.load()
                source = ImageOps.exif_transpose(image).convert("RGBA")
        versions = []
        for cap in (600, 1200):
            version = source.copy()
            version.thumbnail((cap, cap), Image.Resampling.LANCZOS)
            output = BytesIO()
            version.save(output, "WEBP", quality=85, method=6)
            versions.append(output.getvalue())
        return tuple(versions)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValidationError(
            "Choose an image with at most 20 million pixels."
        ) from exc
    except (
        OSError,
        ValueError,
        UnidentifiedImageError,
    ) as exc:
        raise ValidationError(
            "This image cannot be decoded. Choose a complete, uncorrupted JPEG, PNG or WebP."
        ) from exc
