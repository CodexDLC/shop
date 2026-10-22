from decimal import Decimal

import pytest
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from web.catalog.models import Product, ProductVariant, Tag
from web.staff.forms.product_form import ProductForm
from web.staff.models import StaffAuditEvent

pytestmark = pytest.mark.django_db


@pytest.fixture
def product():
    call_command("seed_demo_catalog")
    product = Product.objects.first()
    product.is_active = False
    product.save(update_fields=['is_active'])
    return product


@pytest.fixture
def editor(django_user_model):
    user = django_user_model.objects.create_user(username="model-editor", is_staff=True)
    user.user_permissions.add(*Permission.objects.filter(
        content_type__app_label="catalog", codename__in=["view_product", "add_product", "change_product"],
    ))
    return user


def form_data(product, **changes):
    values = {
        "brand": product.brand_id,
        "category": product.category_id,
        "model_name": product.model_name,
        "manufacturer_article": product.manufacturer_article,
        "slug": product.slug,
        "description_key": product.description_key,
        "tags": list(product.tags.values_list("pk", flat=True)),
        "original_state": ProductForm(instance=product).initial["original_state"],
    }
    values.update(changes)
    return values


def test_new_models_are_drafts_despite_forged_publication(client, editor, product):
    client.force_login(editor)
    assert client.get(reverse("staff:product_add")).status_code == 200
    response = client.post(reverse("staff:product_add"), {
        "brand": product.brand_id, "category": product.category_id,
        "model_name": "Draft Model", "slug": "new-draft", "is_active": "on",
    })
    draft = Product.objects.get(slug="new-draft")
    assert response.status_code == 302
    assert response.url == reverse("staff:product_edit", kwargs={"pk": draft.pk})
    assert draft.is_active is False
    assert draft.variants.count() == 0
    assert StaffAuditEvent.objects.filter(
        actor=editor, action="product.created", object_type="catalog.product", object_id=str(draft.pk),
    ).count() == 1


def test_edit_keeps_draft_and_updates_tags(client, editor, product):
    client.force_login(editor)
    tag = Tag.objects.create(slug="new-editor-tag", label_key="tags.editor")
    response = client.post(reverse("staff:product_edit", kwargs={"pk": product.pk}), form_data(
        product, model_name="Updated Model", manufacturer_article="M2223-2026", tags=[tag.pk], is_active="",
    ))
    assert response.status_code == 302
    product.refresh_from_db()
    assert product.model_name == "Updated Model"
    assert product.manufacturer_article == "M2223-2026"
    assert product.is_active is False
    assert list(product.tags.values_list("pk", flat=True)) == [tag.pk]


def test_form_rejects_duplicate_slug_and_preserves_read_only_legacy_key(product):
    other = Product.objects.exclude(pk=product.pk).first()
    form = ProductForm(form_data(product, slug=other.slug), instance=product)
    assert not form.is_valid()
    assert form.has_error("slug", "unique")
    product.refresh_from_db()
    form = ProductForm(form_data(product, description_key="Ein deutscher Beschreibungstext"), instance=product)
    assert form.is_valid()
    assert form.cleaned_data['description_key'] == product.description_key


def test_stale_edit_cannot_overwrite_newer_product_or_tag_changes(client, editor, product):
    client.force_login(editor)
    stale_data = form_data(product, model_name="Older draft")
    Product.objects.filter(pk=product.pk).update(model_name="Fresh data")
    response = client.post(reverse("staff:product_edit", kwargs={"pk": product.pk}), stale_data)
    assert response.status_code == 400
    product.refresh_from_db()
    assert product.model_name == "Fresh data"
    stale_data = form_data(product)
    tag = Tag.objects.create(slug="concurrent-tag", label_key="tags.concurrent")
    product.tags.add(tag)
    assert client.post(reverse("staff:product_edit", kwargs={"pk": product.pk}), stale_data).status_code == 400
    assert product.tags.filter(pk=tag.pk).exists()
    assert not StaffAuditEvent.objects.exists()


@pytest.mark.parametrize("token", ["", "invalid-token"])
def test_edit_rejects_missing_or_forged_state(client, editor, product, token):
    client.force_login(editor)
    assert client.post(reverse("staff:product_edit", kwargs={"pk": product.pk}), form_data(
        product, model_name="Must not persist", original_state=token,
    )).status_code == 400
    product.refresh_from_db()
    assert product.model_name != "Must not persist"


def test_creation_and_edit_permissions_are_separate(client, django_user_model, product):
    creator = django_user_model.objects.create_user(username="creator-only", is_staff=True)
    creator.user_permissions.add(Permission.objects.get(codename="add_product", content_type__app_label="catalog"))
    client.force_login(creator)
    assert client.get(reverse("staff:product_add")).status_code == 200
    assert client.get(reverse("staff:product_edit", kwargs={"pk": product.pk})).status_code == 403
    assert client.post(reverse("staff:product_edit", kwargs={"pk": product.pk}), {}).status_code == 403
    nonstaff = django_user_model.objects.create_user(username="nonstaff-editor")
    nonstaff.user_permissions.add(*Permission.objects.filter(content_type__app_label="catalog"))
    client.force_login(nonstaff)
    assert client.get(reverse("staff:product_add")).status_code == 403
    assert client.post(reverse("staff:product_add"), {}).status_code == 403


def test_active_model_requires_active_variant_and_edit_missing_is_404(client, editor, product):
    client.force_login(editor)
    product.is_active = True
    product.save(update_fields=['is_active'])
    product.variants.update(is_active=False)
    response = client.post(reverse("staff:product_edit", kwargs={"pk": product.pk}), form_data(product))
    assert response.status_code == 403
    assert client.get(reverse("staff:product_edit", kwargs={"pk": 999999})).status_code == 404


def test_metadata_form_never_changes_variant_values(client, editor, product):
    client.force_login(editor)
    variant = product.variants.first()
    old = variant.price
    response = client.post(reverse("staff:product_edit", kwargs={"pk": product.pk}), form_data(
        product, price="0.01", sku="forged-sku", demo_quantity=99999,
    ))
    assert response.status_code == 302
    assert ProductVariant.objects.get(pk=variant.pk).price == old
    assert not ProductVariant.objects.filter(price=Decimal("0.01")).exists()


def test_model_mutation_requires_csrf(editor, product):
    client = Client(enforce_csrf_checks=True)
    client.force_login(editor)
    assert client.post(reverse("staff:product_edit", kwargs={"pk": product.pk}), form_data(product)).status_code == 403
    assert not StaffAuditEvent.objects.exists()
