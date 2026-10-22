from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.translation import override

from web.catalog.models import Brand, Category, Product, Tag
from web.staff.catalog_workspace.presentation import resource_card, resource_label, safe_photo
from web.staff.models import StaffAuditEvent
from web.staff.operations.presentation import audit_action, money, table_row
from web.staff.operations.selectors import records

pytestmark = pytest.mark.django_db


def operator(*permissions):
    user = get_user_model().objects.create_user(username="card-operator", is_staff=True)
    for permission in permissions:
        app, name = permission.split(".")
        user.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=name))
    return user


@pytest.mark.parametrize("language", ("de", "ru"))
def test_money_is_localized(language):
    with override(language):
        assert money(29.95, "EUR") == "29,95 €"
        assert money(None, "EUR") == "—"


def test_catalog_projection_never_introspects_future_fields_or_keys():
    tag = SimpleNamespace(slug="untranslated-tag", label_key="secret.unresolved.translation", secret="never-render")
    assert resource_label("tags", tag) == "untranslated-tag"
    assert resource_card("tags", tag) == {"values": [], "technical": [
        ("staff.workspace_catalog.field.slug", "untranslated-tag")], "photo": ""}


@pytest.mark.parametrize("url", ("javascript:alert(1)", "//evil.test/a", "http://[broken", "/\\evil.test/a"))
def test_photo_projection_rejects_unsafe_urls(url):
    assert safe_photo(url) == ""


@pytest.mark.parametrize("url", ("https://example.test/a.jpg", "/media/image.jpg"))
def test_photo_projection_accepts_storage_urls(url):
    assert safe_photo(url) == url


def test_tag_pages_show_resolved_name_not_translation_key(client):
    user = operator("catalog.view_tag")
    tag = Tag.objects.create(slug="tag-slug", label_key="colour.black")
    client.force_login(user)
    for path in (reverse("staff:tags"), reverse("staff:tag_detail", kwargs={"pk": tag.pk})):
        html = client.get(path).content.decode()
        assert "colour.black" not in html
        assert "tag-slug" in html


def test_related_products_are_not_loaded_without_product_permission(client):
    user = operator("catalog.view_brand")
    brand = Brand.objects.create(name="Visible brand", slug="visible-brand")
    category = Category.objects.create(slug="hidden-category", name_key="missing.category")
    Product.objects.create(brand=brand, category=category, slug="hidden-product", model_name="Forbidden product")
    client.force_login(user)
    response = client.get(reverse("staff:brand_detail", kwargs={"pk": brand.pk}))
    assert response.status_code == 200
    assert response.context["products"] == []
    assert b"Forbidden product" not in response.content


def test_audit_actions_and_actor_are_bounded_and_permission_scoped(client):
    user = operator("staff.view_staffauditevent")
    actor = get_user_model().objects.create_user(username="private-actor", first_name="Hidden actor")
    event = StaffAuditEvent.objects.create(actor=actor, action="unrecognized.action", object_type="catalog.product", object_id="2")
    client.force_login(user)
    response = client.get(reverse("staff:audit"))
    html = response.content.decode()
    assert "private-actor" not in html and "Hidden actor" not in html
    assert "unrecognized.action" not in html
    html = client.get(reverse("staff:audit_detail", kwargs={"pk": event.pk})).content.decode()
    assert "unrecognized.action" in html and "<details" in html
    assert "Hidden actor" not in html
    user.user_permissions.add(Permission.objects.get(content_type__app_label="auth", codename="view_user"))
    assert "Hidden actor" in client.get(reverse("staff:audit_detail", kwargs={"pk": event.pk})).content.decode()
    with override("ru"):
        assert audit_action("product.publish") == "Товар опубликован"
        assert "unrecognized.action" not in audit_action("unrecognized.action")


def test_audit_list_actor_projection_is_one_query():
    user = operator("staff.view_staffauditevent", "auth.view_user")
    # Warm Django permission cache before measuring the selector and relation projection.
    user.has_perm("auth.view_user")
    StaffAuditEvent.objects.bulk_create([StaffAuditEvent(actor=user, action="product.updated", object_type="catalog.product", object_id=str(i)) for i in range(10)])
    with CaptureQueriesContext(connection) as queries:
        assert len([table_row("audit", obj, user) for obj in records("audit")]) == 10
    assert len(queries) == 1
