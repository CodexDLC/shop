from decimal import Decimal

import pytest
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from web.catalog.models import Product, ProductVariant
from web.staff.views.product_list_view import ProductListView

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff_user(django_user_model):
    user = django_user_model.objects.create_user(username="catalog-reader", is_staff=True)
    user.user_permissions.add(Permission.objects.get(codename="view_product", content_type__app_label="catalog"))
    return user


@pytest.fixture
def catalog():
    call_command("seed_demo_catalog")
    return list(Product.objects.select_related("brand", "category").order_by("pk"))


def product_context(user, parameters=None):
    request = RequestFactory().get("/staff/products/", parameters or {})
    request.user = user
    request.LANGUAGE_CODE = "de"
    view = ProductListView()
    view.setup(request)
    return view.get_context_data()


def test_products_require_staff_and_model_permission(client, django_user_model, staff_user):
    url = reverse("staff:products")
    assert client.get(url).status_code in (302, 403)
    ordinary = django_user_model.objects.create_user(username="ordinary")
    ordinary.user_permissions.add(Permission.objects.get(codename="view_product", content_type__app_label="catalog"))
    client.force_login(ordinary)
    assert client.get(url).status_code == 403
    no_permission = django_user_model.objects.create_user(username="staff-no-permission", is_staff=True)
    client.force_login(no_permission)
    assert client.get(url).status_code == 403
    client.force_login(staff_user)
    assert client.get(url).status_code == 200
    assert client.post(url, {}).status_code == 405


def test_product_filters_match_sku_without_inflating_aggregates(staff_user, catalog):
    product = catalog[0]
    variants = list(product.variants.all())
    variants[0].is_active = False
    variants[0].save(update_fields=["is_active"])
    expected_quantity = sum(variant.demo_quantity for variant in variants[1:])
    context = product_context(staff_user, {
        "q": variants[0].sku,
        "brand": product.brand.slug,
        "category": product.category.slug,
    })
    rows = list(context["products"])
    assert [row.pk for row in rows] == [product.pk]
    assert rows[0].variant_count == len(variants)
    assert rows[0].active_variant_count == len(variants) - 1
    assert rows[0].available_quantity == expected_quantity
    assert rows[0].minimum_price == min(variant.price for variant in variants[1:])
    assert not list(product_context(staff_user, {"brand": "unknown-brand"})["products"])
    assert not list(product_context(staff_user, {"category": "unknown-category"})["products"])


def test_pagination_is_stable_bounded_and_preserves_filters(staff_user, catalog):
    original = catalog[0]
    for index in range(26):
        Product.objects.create(
            slug=f"staff-test-{index}", model_name=f"Staff product {index}",
            brand=original.brand, category=original.category,
        )
    first = product_context(staff_user)
    second = product_context(staff_user, {"page": "2"})
    assert len(first["products"]) == 24
    assert len(second["products"]) == 6
    assert set(row.pk for row in first["products"]).isdisjoint(row.pk for row in second["products"])
    assert product_context(staff_user, {"q": "x" * 300})["search_query"] == "x" * 200
    filtered = product_context(staff_user, {"q": "Staff", "brand": original.brand.slug, "page": "2"})
    assert "page=" not in filtered["page_query"]
    assert "q=Staff" in filtered["page_query"]


def test_empty_and_mixed_currency_products_are_represented_safely(staff_user, catalog):
    original = catalog[0]
    empty = Product.objects.create(
        slug="empty-staff-product", model_name="Empty staff product", is_active=False,
        brand=original.brand, category=original.category,
    )
    ProductVariant.objects.create(
        product=original, sku="STAFF-USD", color_code="red", color_name_key="colors.red",
        size="M", price=Decimal("10"), currency="USD",
    )
    rows = {row.pk: row for row in product_context(staff_user)["products"]}
    assert rows[empty.pk].available_quantity == 0
    assert rows[empty.pk].minimum_price is None
    assert rows[original.pk].currency_count == 2


@pytest.mark.parametrize("extra_products", [0, 15])
def test_product_list_query_budget_does_not_grow_with_rows(staff_user, catalog, extra_products):
    original = catalog[0]
    for index in range(extra_products):
        Product.objects.create(
            slug=f"query-staff-{index}", model_name=f"Staff {index}",
            brand=original.brand, category=original.category,
        )
    with CaptureQueriesContext(connection) as queries:
        context = product_context(staff_user)
        for row in context["products"]:
            assert row.brand.name
            assert row.category.name_key
            assert row.variant_count >= 0
        list(context["brands"])
        list(context["categories"])
    assert len(queries) == 4
