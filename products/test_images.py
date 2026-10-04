"""Image validation, publication, lifecycle and marketing assignments."""

from io import BytesIO, StringIO
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import transaction
from django.urls import reverse
from PIL import Image

from .forms import ProductForm
from .images import MAX_BYTES, optimize_image
from .management.commands.import_product_images import ARTWORK
from .models import Product
from .test_backoffice import product_data

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def isolated_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"


def artwork(size=(800, 400), kind="PNG", mode="RGBA"):
    buffer = BytesIO()
    Image.new(mode, size, (20, 40, 60, 128) if mode == "RGBA" else (20, 40, 60)).save(
        buffer, kind
    )
    return SimpleUploadedFile("misleading.txt", buffer.getvalue(), "text/plain")


@pytest.mark.parametrize(
    "kind,mode", [("PNG", "RGBA"), ("JPEG", "RGB"), ("WEBP", "RGBA")]
)
def test_processing(kind, mode):
    small, large = optimize_image(artwork((1600, 800), kind, mode))
    for content, dimensions in ((small, (600, 300)), (large, (1200, 600))):
        with Image.open(BytesIO(content)) as image:
            assert image.format == "WEBP"
            assert image.size == dimensions
            if mode == "RGBA":
                assert image.getpixel((0, 0))[3] == 128
    assert Image.open(BytesIO(optimize_image(artwork((400, 400)))[1])).size == (
        400,
        400,
    )


@pytest.mark.parametrize("size", [(399, 400), (400, 399), (5001, 4000)])
def test_dimension_limits(size):
    with pytest.raises(ValidationError, match="400|20 million"):
        optimize_image(artwork(size))


def test_bad_content_and_byte_limit():
    for data in (b"not an image", artwork().read()[:100], b"x" * (MAX_BYTES + 1)):
        with pytest.raises(ValidationError):
            optimize_image(SimpleUploadedFile("image.png", data))
    with pytest.raises(ValidationError, match="still JPEG"):
        optimize_image(artwork(kind="BMP", mode="RGB"))
    buffer = BytesIO()
    Image.new("RGBA", (400, 400), "red").save(
        buffer,
        "PNG",
        save_all=True,
        append_images=[Image.new("RGBA", (400, 400), "blue")],
    )
    with pytest.raises(ValidationError, match="Animated"):
        optimize_image(SimpleUploadedFile("animated.png", buffer.getvalue()))


def test_form_validation_does_not_write(category, tmp_path):
    form = ProductForm(product_data(category, price="-1"), {"image": artwork()})
    assert not form.is_valid()
    assert not list(tmp_path.rglob("*.webp"))


def test_staff_lifecycle(
    client, staff_user, product, django_capture_on_commit_callbacks, tmp_path
):
    client.force_login(staff_user)
    url = reverse("products:manage_product_update", args=[product.pk])
    data = product_data(product.category, slug=product.slug)
    assert client.post(url, {**data, "image": artwork()}).status_code == 302
    product.refresh_from_db()
    original = product.image_catalog.name
    assert len(list(tmp_path.rglob("*.webp"))) == 2
    assert client.post(url, data).status_code == 302
    product.refresh_from_db()
    assert product.image_catalog.name == original
    assert (
        client.post(
            url, {**data, "image": SimpleUploadedFile("bad.png", b"bad")}
        ).status_code
        == 200
    )
    product.refresh_from_db()
    assert product.image_catalog.name == original
    with django_capture_on_commit_callbacks(execute=True):
        assert client.post(url, {**data, "image": artwork()}).status_code == 302
    assert not product.image_catalog.storage.exists(original)
    with django_capture_on_commit_callbacks(execute=True):
        assert client.post(url, {**data, "remove_image": "on"}).status_code == 302
    product.refresh_from_db()
    assert not product.image_catalog
    assert not list(tmp_path.rglob("*.webp"))


def test_storage_failure_is_inline_and_preserves_pair(product, tmp_path):
    product.prepare_image(optimize_image(artwork()))
    product.save()
    old = product.image_catalog.name
    storage = product.image_catalog.storage
    save = storage.save
    calls = 0

    def fail_second(name, content, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("disk full")
        return save(name, content, **kwargs)

    with patch.object(storage, "save", side_effect=fail_second):
        form = ProductForm(
            product_data(product.category, slug=product.slug),
            {"image": artwork()},
            instance=product,
        )
        assert not form.is_valid()
        assert "could not be stored" in str(form.errors)
    product.refresh_from_db()
    assert product.image_catalog.name == old
    assert len(list(tmp_path.rglob("*.webp"))) == 2


def test_rollback_preserves_old_files(product):
    product.prepare_image(optimize_image(artwork()))
    product.save()
    old = product.image_catalog.name
    with pytest.raises(RuntimeError), transaction.atomic():
        product.prepare_image(optimize_image(artwork()))
        product.save()
        raise RuntimeError("rollback")
    product.refresh_from_db()
    assert product.image_catalog.name == old
    assert product.image_catalog.storage.exists(old)


def test_delete_cleans_pair(product, django_capture_on_commit_callbacks, tmp_path):
    product.prepare_image(optimize_image(artwork()))
    product.save()
    with django_capture_on_commit_callbacks(execute=True):
        Product.objects.filter(pk=product.pk).delete()
    assert not list(tmp_path.rglob("*.webp"))


def test_render_and_independent_fallback(client, product):
    product.prepare_image(optimize_image(artwork()))
    product.save()
    for url in (reverse("products:catalog"), product.category.get_absolute_url()):
        html = client.get(url).content.decode()
        assert product.image_catalog.url in html
        assert 'loading="lazy"' in html
        assert "object-contain" in html
    html = client.get(product.get_absolute_url()).content.decode()
    assert product.image_detail.url in html
    assert 'loading="lazy"' not in html
    product.image_catalog.storage.delete(product.image_catalog.name)
    assert "placeholders/home-assistants.svg" in product.catalog_image_url
    assert product.image_detail.url == product.detail_image_url
    product.image_detail.storage.delete(product.image_detail.name)
    assert (
        "placeholders/home-assistants.svg"
        in client.get(product.get_absolute_url()).content.decode()
    )
    product.category.slug = "unknown"
    assert product.catalog_image_url.endswith("placeholders/default.svg")


def test_admin_upload_replace_remove(
    client, staff_user, product, django_capture_on_commit_callbacks
):
    staff_user.is_superuser = True
    staff_user.save()
    client.force_login(staff_user)
    url = reverse("admin:products_product_change", args=[product.pk])
    data = product_data(product.category, slug=product.slug, _save="Save")
    for change in ({"image": artwork()}, {"image": artwork()}, {"remove_image": "on"}):
        with django_capture_on_commit_callbacks(execute=True):
            response = client.post(url, {**data, **change})
        assert response.status_code == 302
    product.refresh_from_db()
    assert not product.image_catalog
    assert (
        client.post(
            url, {**data, "image": SimpleUploadedFile("bad.jpg", b"bad")}
        ).status_code
        == 200
    )


def test_import_mapping_rerun_and_failures(category, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    for filename, slug in ARTWORK.items():
        Product.objects.create(name=slug, slug=slug, category=category, price=1)
        (source / filename).write_bytes(artwork().read())
    unmapped = Product.objects.create(
        name="variant", slug="soulsear-mark-ii", category=category, price=1
    )
    (source / "SyncRest GPT Text.png").write_bytes(b"unused")
    (source / "RecallPro.png").write_bytes(b"corrupt")
    (source / "Veil GPT Text.png").unlink()
    Product.objects.filter(slug="hush").delete()
    report, errors = StringIO(), StringIO()
    call_command("import_product_images", source=source, stdout=report, stderr=errors)
    assert "Imported: 9; skipped: 0; failed: 3" in report.getvalue()
    assert "Missing target product: hush" in errors.getvalue()
    assert Product.objects.get(slug="soulsear-mark-i").image_catalog
    assert Product.objects.get(slug="syncrest").image_catalog
    assert not unmapped.image_catalog
    assert (source / "SyncRest GPT No Text.png").read_bytes() == artwork().read()
    report = StringIO()
    call_command(
        "import_product_images", source=source, stdout=report, stderr=StringIO()
    )
    assert "skipped: 9" in report.getvalue()


@pytest.mark.parametrize(
    "kind,mode", [("PNG", "RGBA"), ("JPEG", "RGB"), ("WEBP", "RGBA")]
)
def test_staff_create_upload(client, staff_user, category, kind, mode):
    client.force_login(staff_user)
    response = client.post(
        reverse("products:manage_product_create"),
        {
            **product_data(category),
            "image": artwork(kind=kind, mode=mode),
        },
    )
    assert response.status_code == 302
    product = Product.objects.get(slug="mindsync-sleep-halo")
    assert product.image_catalog.storage.exists(product.image_catalog.name)
    assert product.image_detail.storage.exists(product.image_detail.name)


def test_byte_boundary():
    content = artwork().read()
    exact = content + b"\0" * (MAX_BYTES - len(content))
    assert optimize_image(SimpleUploadedFile("boundary.png", exact))
    with pytest.raises(ValidationError, match="10 MiB"):
        optimize_image(SimpleUploadedFile("boundary.png", exact + b"\0"))


def test_render_has_no_image_processing_or_added_queries(
    client, product, django_assert_num_queries
):
    # Compare the same catalog before/after adding files, rather than pinning the
    # catalog's unrelated context/auth query count.
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as baseline:
        client.get(reverse("products:catalog"))
    product.prepare_image(optimize_image(artwork()))
    product.save()
    with (
        patch(
            "products.images.Image.open",
            side_effect=AssertionError("request decoded image"),
        ),
        django_assert_num_queries(len(baseline)),
    ):
        assert client.get(reverse("products:catalog")).status_code == 200


def test_prune_preserves_references_and_recent_files(product, tmp_path):
    import os

    product.prepare_image(optimize_image(artwork()))
    product.save()
    directory = tmp_path / "media" / "products"
    old = directory / "orphan-catalog.webp"
    old.write_bytes(b"orphan")
    os.utime(old, (0, 0))
    recent = directory / "recent-detail.webp"
    recent.write_bytes(b"staged")
    report = StringIO()
    call_command("prune_product_images", stdout=report)
    assert "orphan-catalog.webp" in report.getvalue()
    assert old.exists()
    call_command("prune_product_images", delete=True, stdout=StringIO())
    assert not old.exists()
    assert recent.exists()
    assert product.image_catalog.storage.exists(product.image_catalog.name)
