import io
import re
from unittest.mock import patch

import pytest
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection
from django.test import Client, RequestFactory, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.translation import override
from PIL import Image

from web.cart.session_cart import quote
from web.catalog.adapters.variant_selection import CatalogVariantSelection
from web.catalog.listing_request import ListingRequest
from web.catalog.models import Brand, Category, Product, ProductVariant
from web.catalog.navigation import header_section_visibility
from web.catalog.selectors import catalog_products, listing_facets, listing_products, storefront_products
from web.staff.catalog_workspace.category_form import CategoryForm
from web.staff.catalog_workspace.category_tree import category_rows, tree_rows
from web.staff.forms.product_form import ProductForm
from web.staff.models import StaffAuditEvent

pytestmark = pytest.mark.django_db


@pytest.fixture
def editor(django_user_model):
    user = django_user_model.objects.create_user(username="category-editor", is_staff=True)
    user.user_permissions.add(*Permission.objects.filter(content_type__app_label="catalog"))
    return user


@pytest.fixture
def tree():
    root = Category.objects.create(slug="underwear-root", name_key="catalog.category.underwear-root",
                                   name_de="Unterwäsche", section="underwear")
    child = Category.objects.create(slug="briefs", name_key="catalog.category.briefs",
                                    name_de="Slips", parent=root, section="underwear")
    brand = Brand.objects.create(slug="category-test", name="Category brand")
    product = Product.objects.create(slug="category-product", model_name="Test slip", category=child, brand=brand)
    ProductVariant.objects.create(product=product, sku="CATEGORY-1", size="M", color_code="black",
                                  color_name_key="black", price="12.00", demo_quantity=3)
    return root, child, product


def form_data(category=None, **changes):
    data = {"name_de": category.name_de if category else "Neue Kategorie",
            "slug": category.slug if category else "new-category", "section": "underwear",
            "position": "0", "is_visible": "on", "parent": category.parent_id or "" if category else ""}
    data.update(changes)
    return data


def edit(client, category, **changes):
    url = reverse("staff:category_edit", kwargs={"pk": category.pk})
    token = client.get(url).context["original_state"]
    return client.post(url, form_data(category, original_state=token, **changes))


def test_category_tree_cycle_and_section_validation(tree):
    root, child, _ = tree
    root.parent = child
    with pytest.raises(ValidationError) as error:
        root.full_clean()
    assert "parent" in error.value.message_dict
    root.parent = None
    root.section = "swimwear"
    with pytest.raises(ValidationError) as error:
        root.full_clean()
    assert "section" in error.value.message_dict
    child.parent = child
    with pytest.raises(ValidationError) as error:
        child.full_clean()
    assert "parent" in error.value.message_dict


def test_tree_counts_order_names_and_query_budget(tree):
    root, child, _ = tree
    other = Category.objects.create(slug="first", name_de="Erste", position=0)
    root.position = 10
    root.save()
    with CaptureQueriesContext(connection) as captured:
        rows = tree_rows(category_rows())
        assert [row["object"].pk for row in rows] == [other.pk, root.pk, child.pk]
        assert rows[-1]["path"] == "Unterwäsche / Slips"
        assert rows[-1]["object"].product_count == 1
    assert len(captured) == 1
    child.name_ru = "Трусы"
    with override("ru"):
        assert child.name == "Трусы"
    with override("de"):
        assert child.name == "Slips"
    assert Category(slug="human-readable", name_key="unknown.category").name == "Human readable"


def test_public_visibility_inherits_ancestors_without_changing_product(tree):
    root, child, product = tree
    assert list(catalog_products(category=root.slug)) == [product]
    assert list(listing_products(ListingRequest(filters={"category": [root.slug]}))) == [product]
    root.is_visible = False
    root.save()
    assert not storefront_products().exists()
    assert not listing_products(ListingRequest()).exists()
    assert listing_facets()["categories"] == []
    assert not header_section_visibility()["underwear"]
    with pytest.raises(Product.DoesNotExist):
        CatalogVariantSelection().select(product_slug=product.slug, color="black", size="M")
    request = RequestFactory().get("/")
    result = quote(request, values={"CATEGORY-1": 1}, ignore_coupon=True)
    assert not result["can_checkout"]
    product.refresh_from_db()
    assert product.is_active and product.category_id == child.pk
    root.is_visible = True
    root.save()
    assert storefront_products().filter(pk=product.pk).exists()


def test_public_selector_keeps_four_queries_and_corrupt_cycle_fails_closed(tree):
    root, child, product = tree
    with CaptureQueriesContext(connection) as captured:
        assert list(storefront_products()) == [product]
    assert len(captured) == 4
    Category.objects.filter(pk=root.pk).update(parent_id=child.pk)
    assert not storefront_products().exists()


def test_category_create_edit_tree_stale_audit_and_slug_preservation(client, editor, tree):
    root, child, _ = tree
    client.force_login(editor)
    url = reverse("staff:category_add")
    token = client.get(url).context["original_state"]
    response = client.post(url, form_data(original_state=token, parent=root.pk))
    assert response.status_code == 302
    category = Category.objects.get(slug="new-category")
    assert category.parent_id == root.pk and category.name_key == "catalog.category.new-category"
    edit_url = reverse("staff:category_edit", kwargs={"pk": child.pk})
    state = client.get(edit_url).context["original_state"]
    response = client.post(edit_url, form_data(child, name_de="Neue Slips", slug="tampered", original_state=state))
    assert response.status_code == 302
    child.refresh_from_db()
    assert child.name_de == "Neue Slips" and child.slug == "briefs"
    assert client.post(edit_url, form_data(child, name_de="Stale", original_state=state)).status_code == 400
    assert StaffAuditEvent.objects.filter(action="reference.category.saved").count() == 2
    assert edit(client, root, parent=child.pk, confirm_visibility="on").status_code == 400


def test_visibility_and_reparent_need_publish_permission_and_ack(client, editor, tree):
    root, child, product = tree
    client.force_login(editor)
    assert edit(client, root, is_visible="").status_code == 400
    permission = Permission.objects.get(codename="publish_product")
    editor.user_permissions.remove(permission)
    assert edit(client, root, is_visible="", confirm_visibility="on").status_code == 400
    # Ordinary category content is independently editable even with published products.
    assert edit(client, child, description_de="Neue Beschreibung").status_code == 302
    editor.user_permissions.add(permission)
    assert edit(client, root, is_visible="", confirm_visibility="on").status_code == 302
    root.refresh_from_db()
    assert not root.is_visible
    product.refresh_from_db()
    assert product.is_active
    another = Category.objects.create(slug="hidden", name_de="Hidden", section="underwear", is_visible=False)
    assert edit(client, child, parent=another.pk).status_code == 400
    assert edit(client, child, parent=another.pk, confirm_visibility="on").status_code == 302


def test_category_permissions_csrf_private_preview_and_assignment_entry(client, editor, tree, django_user_model):
    root, _, _ = tree
    client.force_login(editor)
    preview = client.get(reverse("staff:category_preview", kwargs={"pk": root.pk}))
    assert preview.status_code == 200
    assert preview["X-Robots-Tag"] == "noindex, nofollow"
    assert preview["Cache-Control"] == "private, no-store"
    empty = Category.objects.create(slug="empty-category", name_de="Empty")
    response = client.get(reverse("staff:category_detail", kwargs={"pk": empty.pk}))
    assert (reverse("staff:products") + "?state=draft").encode() in response.content
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(editor)
    assert csrf_client.post(reverse("staff:category_add"), form_data()).status_code == 403
    user = django_user_model.objects.create_user(username="no-category-perms", is_staff=True)
    client.force_login(user)
    for name in ("category_detail", "category_edit", "category_preview"):
        assert client.get(reverse(f"staff:{name}", kwargs={"pk": root.pk})).status_code == 403
    assert client.get(reverse("staff:category_add")).status_code == 403
    user.user_permissions.add(*Permission.objects.filter(content_type__app_label="catalog"))
    user.is_staff = False
    user.save()
    assert client.get(reverse("staff:categories")).status_code == 403


def image_upload():
    stream = io.BytesIO()
    Image.new("RGB", (10, 10), "red").save(stream, format="PNG")
    return SimpleUploadedFile("unsafe-name.svg", stream.getvalue(), content_type="image/svg+xml")


def test_category_photo_sanitization_and_replacement_preserve_old_file(client, editor, tree, tmp_path):
    _, child, _ = tree
    client.force_login(editor)
    with override_settings(MEDIA_ROOT=tmp_path):
        assert edit(client, child, upload=SimpleUploadedFile("bad.svg", b"<svg/>")).status_code == 400
        assert edit(client, child, upload=image_upload()).status_code == 302
        child.refresh_from_db()
        old_name = child.image.name
        assert old_name.startswith("categories/") and old_name.endswith(".jpg")
        with child.image.open() as image_file:
            assert Image.open(image_file).format == "JPEG"
        assert edit(client, child, upload=image_upload()).status_code == 302
        child.refresh_from_db()
        assert child.image.name != old_name
        assert child.image.storage.exists(old_name)
        assert edit(client, child, remove_image="on").status_code == 302
        child.refresh_from_db()
        assert not child.image


def test_photo_is_cleaned_if_database_audit_rolls_back(client, editor, tree, tmp_path):
    _, child, _ = tree
    client.force_login(editor)
    with override_settings(MEDIA_ROOT=tmp_path), patch(
        "web.staff.catalog_workspace.category_edit_view.record_staff_action", side_effect=IntegrityError,
    ):
        assert edit(client, child, upload=image_upload()).status_code == 400
    child.refresh_from_db()
    assert not child.image
    assert not list(tmp_path.rglob("*.jpg"))


def test_parent_choices_product_breadcrumb_and_admin_cannot_bypass(tree, editor):
    root, child, product = tree
    form = CategoryForm(instance=root, categories=category_rows())
    assert child.pk not in [choice[0] for choice in form.fields["parent"].choices]
    product.is_active = False
    product.save()
    choices = dict(ProductForm(instance=product).fields["category"].choices)
    assert choices[child.pk] == "Unterwäsche / Slips"
    request = RequestFactory().get("/")
    request.user = editor
    model_admin = admin.site._registry[Category]
    assert not model_admin.has_change_permission(request, root)
    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_delete_permission(request, root)


def test_category_content_binds_to_public_listing_and_seo(client, tree):
    root, _, _ = tree
    root.description_de = "Kategoriebeschreibung"
    root.seo_title = "Unterwäsche kaufen"
    root.seo_description = "Beschreibung für Suchmaschinen"
    root.save()
    response = client.get(reverse("catalog:list"), {"category": root.slug})
    assert response.status_code == 200
    assert response.context["catalog_listing"]["total"] == 1
    assert root.description_de.encode() in response.content
    assert root.seo_title in response.context["seo"]["title"]
    assert response.context["seo"]["description"] == root.seo_description
    assert response.context["seo"]["robots"] == "noindex, nofollow"


def test_staff_count_link_category_filter_is_not_a_public_category_metadata_object(client, editor, tree):
    _, child, product = tree
    child.name_key = "catalog.category.new-no-legacy-translation"
    child.name_de = "Neue Kategorie"
    child.save()
    client.force_login(editor)
    response = client.get(reverse("staff:products"), {"category": child.slug})
    assert response.status_code == 200
    assert response.context["selected_category"] == child.slug
    assert list(response.context["products"])[0].pk == product.pk
    assert response.content.decode().count("Neue Kategorie") >= 2
    assert "[catalog.category." not in response.content.decode()


@pytest.mark.parametrize("language", ["de", "ru"])
def test_rendered_category_screens_and_validation_do_not_leak_translation_keys(client, editor, tree, language):
    root, _, _ = tree
    client.force_login(editor)
    with override(language):
        for name in ("categories", "category_add", "category_detail", "category_edit", "category_preview"):
            kwargs = {"pk": root.pk} if name in ("category_detail", "category_edit", "category_preview") else {}
            response = client.get(reverse(f"staff:{name}", kwargs=kwargs))
            assert response.status_code == 200
            assert not re.search(r"\[staff\.[^\]]+\]", response.content.decode()), name
            if name in ("category_add", "category_edit"):
                assert b"[staff.workspace_catalog.save]" not in response.content
        url = reverse("staff:category_add")
        token = client.get(url).context["original_state"]
        response = client.post(url, form_data(name_de="", original_state=token))
        assert response.status_code == 400
        assert not re.search(r"\[staff\.[^\]]+\]", response.content.decode())
