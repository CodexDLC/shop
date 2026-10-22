import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse

from web.catalog.models import Brand, Category, Product, ProductVariant
from web.staff.models import StaffAuditEvent

pytestmark = pytest.mark.django_db


@pytest.fixture
def variant_editor(client):
    user = get_user_model().objects.create_user(username="variant-editor", is_staff=True)
    user.user_permissions.add(*Permission.objects.filter(content_type__app_label="catalog",
                                                        codename__in=["change_product", "change_productvariant",
                                                                      "add_productvariant"]))
    client.force_login(user)
    product = Product.objects.create(slug="matrix", model_name="Matrix",
                                     is_active=False,
                                     brand=Brand.objects.create(slug="matrix", name="Matrix"),
                                     category=Category.objects.create(slug="matrix", name_key="matrix"))
    variant = ProductVariant.objects.create(product=product, sku="matrix-black-m", color_code="black",
                                            color_name_key="black", color_hex="#000000", size="M",
                                            price="12.50", currency="EUR", demo_quantity=0)
    return client, user, product, variant


def editor_data(client, product):
    response = client.get(reverse("staff:variants", kwargs={"pk": product.pk}))
    rows = response.context["formset"].initial
    data = {"fingerprint": response.context["fingerprint"], "variants-TOTAL_FORMS": str(len(rows) + 1),
            "variants-INITIAL_FORMS": str(len(rows)), "variants-MAX_NUM_FORMS": "100"}
    for index, row in enumerate(rows):
        for name, value in row.items():
            if value is not False:
                data[f"variants-{index}-{name}"] = str(value)
    return data


def add_row(data, *, sku="matrix-navy-l", color="navy", size="L"):
    data.update({f"variants-1-{name}": value for name, value in {
        "sku": sku, "color_code": color, "color_name_key": "navy", "color_hex": "#112233",
        "size": size, "price": "19.95", "currency": "EUR", "demo_quantity": "0", "is_active": "on",
    }.items()})


def test_update_create_and_immutable_existing_sku(variant_editor):
    client, _, product, variant = variant_editor
    data = editor_data(client, product)
    data["variants-0-price"] = "15.50"
    data["variants-0-sku"] = "tampered"
    add_row(data)
    assert client.post(reverse("staff:variants", kwargs={"pk": product.pk}), data).status_code == 302
    variant.refresh_from_db()
    assert str(variant.price) == "15.50"
    assert variant.sku == "matrix-black-m"
    assert product.variants.count() == 2
    assert product.variants.get(sku="matrix-navy-l").demo_quantity == 0
    assert StaffAuditEvent.objects.filter(action="variants.updated", object_id=str(product.pk)).count() == 1


def test_stale_post_writes_nothing(variant_editor):
    client, _, product, variant = variant_editor
    data = editor_data(client, product)
    ProductVariant.objects.filter(pk=variant.pk).update(demo_quantity=3)
    data["variants-0-price"] = "99.99"
    response = client.post(reverse("staff:variants", kwargs={"pk": product.pk}), data)
    assert response.status_code == 409
    variant.refresh_from_db()
    assert str(variant.price) == "12.50"
    assert variant.demo_quantity == 3
    assert not StaffAuditEvent.objects.exists()
    assert response.context["fingerprint"] == data["fingerprint"]
    assert client.post(reverse("staff:variants", kwargs={"pk": product.pk}), data).status_code == 409


@pytest.mark.parametrize("kind", ["sku", "combination", "currency", "id", "missing", "maximum"])
def test_invalid_rows_never_write(variant_editor, kind):
    client, _, product, variant = variant_editor
    data = editor_data(client, product)
    if kind == "sku":
        add_row(data, sku=variant.sku)
    elif kind == "combination":
        add_row(data, color="black", size="M")
    elif kind == "currency":
        add_row(data)
        data["variants-1-currency"] = "USD"
    elif kind == "id":
        data["variants-0-id"] = str(variant.pk + 100)
    elif kind == "missing":
        data["variants-TOTAL_FORMS"] = "0"
        data["variants-INITIAL_FORMS"] = "0"
    else:
        data["variants-TOTAL_FORMS"] = "101"
    assert client.post(reverse("staff:variants", kwargs={"pk": product.pk}), data).status_code == 400
    assert product.variants.count() == 1


def test_add_requires_separate_permission(variant_editor):
    client, user, product, _ = variant_editor
    user.user_permissions.remove(Permission.objects.get(content_type__app_label="catalog",
                                                        codename="add_productvariant"))
    data = editor_data(client, product)
    add_row(data)
    assert client.post(reverse("staff:variants", kwargs={"pk": product.pk}), data).status_code == 400
    assert product.variants.count() == 1


def test_permissions_required(variant_editor):
    client, user, product, _ = variant_editor
    url = reverse("staff:variants", kwargs={"pk": product.pk})
    client.logout()
    assert client.get(url).status_code == 302
    user.user_permissions.clear()
    client.force_login(user)
    assert client.get(url).status_code == 403


def test_foreign_variant_id_rejected(variant_editor):
    client, _, product, variant = variant_editor
    other = Product.objects.create(slug="other", model_name="Other", brand=product.brand,
                                   category=product.category)
    foreign = ProductVariant.objects.create(product=other, sku="foreign", color_code="black",
                                            color_name_key="black", size="M", price="7.00")
    data = editor_data(client, product)
    data["variants-0-id"] = str(foreign.pk)
    data["variants-0-price"] = "99.00"
    assert client.post(reverse("staff:variants", kwargs={"pk": product.pk}), data).status_code == 400
    foreign.refresh_from_db()
    variant.refresh_from_db()
    assert str(foreign.price) == "7.00" and str(variant.price) == "12.50"


def test_customer_with_model_permissions_still_forbidden(variant_editor):
    client, user, product, _ = variant_editor
    user.is_staff = False
    user.save(update_fields=["is_staff"])
    assert client.get(reverse("staff:variants", kwargs={"pk": product.pk})).status_code == 403


@pytest.mark.parametrize("field,value", [("price", "-1"), ("currency", "eur"),
                                          ("color_hex", "red"), ("demo_quantity", "-1")])
def test_invalid_values_rejected(variant_editor, field, value):
    client, _, product, _ = variant_editor
    data = editor_data(client, product)
    data[f"variants-0-{field}"] = value
    assert client.post(reverse("staff:variants", kwargs={"pk": product.pk}), data).status_code == 400


def test_published_product_cannot_lose_all_active_variants(variant_editor):
    client, _, product, variant = variant_editor
    product.is_active = True
    product.save(update_fields=['is_active'])
    data = editor_data(client, product)
    data.pop("variants-0-is_active")
    data["variants-0-price"] = "99.00"
    assert client.post(reverse("staff:variants", kwargs={"pk": product.pk}), data).status_code == 403
    variant.refresh_from_db()
    assert variant.is_active and str(variant.price) == "12.50"
    assert not StaffAuditEvent.objects.exists()


def test_draft_product_allows_inactive_variants(variant_editor):
    client, _, product, variant = variant_editor
    product.is_active = False
    product.save(update_fields=["is_active"])
    data = editor_data(client, product)
    data.pop("variants-0-is_active")
    assert client.post(reverse("staff:variants", kwargs={"pk": product.pk}), data).status_code == 302
    variant.refresh_from_db()
    assert not variant.is_active


def test_color_name_requires_translation_key(variant_editor):
    client, _, product, _ = variant_editor
    data = editor_data(client, product)
    data["variants-0-color_name_key"] = "Dark Navy"
    assert client.post(reverse("staff:variants", kwargs={"pk": product.pk}), data).status_code == 400


def test_empty_form_has_no_id_and_many_new_rows_can_be_saved(variant_editor):
    client, _, product, _ = variant_editor
    response = client.get(reverse("staff:variants", kwargs={"pk": product.pk}))
    assert response.context["formset"].empty_form["id"].value() is None
    assert response.context["formset"].forms[-1]["id"].value() is None
    assert 'id="variant-add-row"' in response.content.decode()
    assert 'id="variant-empty-row"' in response.content.decode()
    data = editor_data(client, product)
    data["variants-TOTAL_FORMS"] = "13"
    for index in range(1, 13):
        temporary = {}
        add_row(temporary, sku=f"new-{index}", size=f"S{index}")
        data.update({name.replace("variants-1-", f"variants-{index}-"): value
                     for name, value in temporary.items()})
    assert client.post(reverse("staff:variants", kwargs={"pk": product.pk}), data).status_code == 302
    assert product.variants.count() == 13
