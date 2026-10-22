import io
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from PIL import Image

from web.catalog.models import Brand, Category, Product, ProductImage, ProductVariant
from web.staff.models import StaffAuditEvent
from web.staff.photo_uploads import MAX_UPLOAD_BYTES, sanitize_photo

pytestmark = pytest.mark.django_db


@pytest.fixture
def editor(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.MEDIA_URL = "/media/"
    user = get_user_model().objects.create_user(username="media-editor", is_staff=True)
    user.user_permissions.add(*Permission.objects.filter(content_type__app_label="catalog"))
    client.force_login(user)
    product = Product.objects.create(slug="photos", model_name="Photos", is_active=False,
                                     brand=Brand.objects.create(slug="photos", name="Photos"),
                                     category=Category.objects.create(slug="photos", name_key="photos"))
    ProductVariant.objects.create(product=product, sku="photos-m", color_code="black",
                                  color_name_key="black", size="M", price="19.95")
    return client, user, product, tmp_path


def upload(fmt="PNG", name="../../untrusted.html", **options):
    stream = io.BytesIO()
    Image.new("RGB", (16, 12), "red").save(stream, format=fmt, **options)
    return SimpleUploadedFile(name, stream.getvalue(), content_type="text/html")


def url(product):
    return reverse("staff:product_photos", kwargs={"pk": product.pk})


def data(client, product, **extra):
    response = client.get(url(product))
    assert response.status_code == 200
    return {"original_state": response.context["original_state"], "action": "create", "color_code": "black",
            "position": "0", "alt_text": "Rotes Foto", **extra}


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP"])
def test_real_bytes_reencoded_uuid_and_local_url(editor, fmt):
    client, _, product, root = editor
    response = client.post(url(product), data(client, product, upload=upload(fmt)))
    assert response.status_code == 302
    image = product.images.get()
    assert image.file.name.startswith("products/") and image.file.name.endswith(".jpg")
    assert "html" not in image.file.name
    assert image.public_url.startswith("/media/products/")
    with Image.open(root / image.file.name) as saved:
        assert saved.format == "JPEG" and saved.size == (16, 12)
        assert not saved.getexif()
    assert StaffAuditEvent.objects.filter(action="photos.create").exists()


@pytest.mark.parametrize("payload", [b"<svg xmlns='http://www.w3.org/2000/svg'/>", b"<html>bad</html>", b"garbage"])
def test_bad_files_rejected_without_storage_or_db_writes(editor, payload):
    client, _, product, root = editor
    response = client.post(url(product), data(client, product,
                           upload=SimpleUploadedFile("photo.jpg", payload, content_type="image/jpeg")))
    assert response.status_code == 400
    assert not product.images.exists() and not list(root.rglob("*"))


def test_frames_pixels_bytes_and_metadata_are_checked(editor):
    from django.core.exceptions import ValidationError
    too_big = SimpleUploadedFile("big.png", b"x")
    too_big.size = MAX_UPLOAD_BYTES + 1
    with pytest.raises(ValidationError):
        sanitize_photo(too_big)
    with patch("web.staff.photo_uploads.MAX_PIXELS", 10), pytest.raises(ValidationError):
        sanitize_photo(upload())
    stream = io.BytesIO()
    Image.new("RGB", (2, 2), "red").save(stream, format="PNG", save_all=True,
                                         append_images=[Image.new("RGB", (2, 2), "blue")])
    with pytest.raises(ValidationError):
        sanitize_photo(SimpleUploadedFile("animation.png", stream.getvalue()))
    exif = Image.Exif()
    exif[0x010E] = "secret metadata"
    clean = sanitize_photo(upload("JPEG", exif=exif))
    assert b"secret metadata" not in clean.read()


def test_legacy_url_preserved_update_swap_color_and_delete(editor):
    client, _, product, _ = editor
    first = ProductImage.objects.create(product=product, color_code="black", position=0,
                                        image_url="https://example.test/first.jpg", alt_key="legacy.first")
    second = ProductImage.objects.create(product=product, color_code="black", position=1,
                                         image_url="https://example.test/second.jpg", alt_key="legacy.second")
    assert first.public_url == first.image_url
    response = client.post(url(product), data(client, product, action="update", image_id=second.pk,
                                            position="0"))
    assert response.status_code == 302
    first.refresh_from_db()
    second.refresh_from_db()
    assert (first.position, second.position) == (1, 0)
    assert second.image_url.endswith("second.jpg") and second.alt_key == "legacy.second"
    assert client.post(url(product), data(client, product, action="update", image_id=second.pk,
                                         color_code="")).status_code == 302
    second.refresh_from_db()
    assert second.color_code == ""
    assert client.post(url(product), data(client, product, action="delete", image_id=second.pk)).status_code == 302
    assert not ProductImage.objects.filter(pk=second.pk).exists()


def test_invalid_colour_stale_and_cross_parent(editor):
    client, _, product, _ = editor
    assert client.post(url(product), data(client, product, color_code="invented", upload=upload())).status_code == 400
    stale = data(client, product, upload=upload())
    Product.objects.filter(pk=product.pk).update(model_name="Changed")
    assert client.post(url(product), stale).status_code == 409
    assert client.post(url(product), stale).status_code == 409
    assert client.post(url(product), data(client, product, action="delete", image_id=999999)).status_code == 404
    assert client.post(url(product), data(client, product, action="delete", image_id="invalid")).status_code == 404
    other = Product.objects.create(slug="other-photo-parent", brand=product.brand, category=product.category,
                                   model_name="Other", is_active=False)
    foreign_image = ProductImage.objects.create(product=other, image_url="https://example.test/other.jpg")
    assert client.post(url(product), data(client, product, action="delete", image_id=foreign_image.pk)).status_code == 404
    assert ProductImage.objects.filter(pk=foreign_image.pk).exists()
    assert not product.images.exists()


def test_upload_db_failure_cleans_new_file_and_old_file_is_retained(editor):
    client, _, product, root = editor
    with patch("web.staff.views.product_photos_view.mark_changed", side_effect=IntegrityError):
        assert client.post(url(product), data(client, product, upload=upload())).status_code == 409
    assert not product.images.exists()
    assert not [path for path in root.rglob("*") if path.is_file()]
    assert client.post(url(product), data(client, product, upload=upload())).status_code == 302
    image = product.images.get()
    old_name = image.file.name
    assert client.post(url(product), data(client, product, action="update", image_id=image.pk,
                                         upload=upload())).status_code == 302
    assert (root / old_name).exists()
    image.refresh_from_db()
    assert image.file.name != old_name
    retained = image.file.name
    assert client.post(url(product), data(client, product, action="delete", image_id=image.pk)).status_code == 302
    assert (root / retained).exists()


def test_permissions_published_get_no_mutation_and_csrf(editor):
    client, user, product, _ = editor
    response = client.get(url(product))
    assert response["Cache-Control"] == "no-store, private" and "noindex" in response["X-Robots-Tag"]
    assert not product.images.exists()


def test_csrf_create_permission_and_published_lock(editor):
    client, user, product, _ = editor
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(user)
    assert csrf_client.post(url(product), data(client, product, upload=upload())).status_code == 403
    user.user_permissions.remove(Permission.objects.get(content_type__app_label="catalog", codename="add_productimage"))
    assert client.post(url(product), data(client, product, upload=upload())).status_code == 403
    user.user_permissions.add(Permission.objects.get(content_type__app_label="catalog", codename="add_productimage"))
    Product.objects.filter(pk=product.pk).update(is_active=True)
    assert client.post(url(product), data(client, product, upload=upload())).status_code == 403
    assert not product.images.exists()


def test_gallery_form_queries_do_not_grow_with_photos(editor):
    client, _, product, _ = editor
    ProductImage.objects.create(product=product, image_url="https://example.test/1.jpg")
    client.get(url(product))  # Warm translation/template caches before measuring.
    with CaptureQueriesContext(connection) as one:
        assert client.get(url(product)).status_code == 200
    ProductImage.objects.bulk_create([ProductImage(product=product, position=index,
                                    image_url=f"https://example.test/{index}.jpg") for index in range(1, 10)])
    with CaptureQueriesContext(connection) as ten:
        assert client.get(url(product)).status_code == 200
    assert len(ten) == len(one)
