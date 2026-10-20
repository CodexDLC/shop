from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.auth.models import Permission
from django.http import QueryDict
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from web.catalog.listing_request import ListingRequest
from web.catalog.models import Brand, Category, Product, ProductVariant
from web.catalog.views import CatalogPageView
from web.staff.forms.product_form import ProductForm

pytestmark = pytest.mark.django_db


@pytest.fixture
def sections():
    brand = Brand.objects.create(slug="brand", name="Brand")
    underwear = Category.objects.create(slug="underwear", name_key="Underwear", section="underwear")
    swimwear = Category.objects.create(slug="swimwear", name_key="Swimwear", section="swimwear")
    products = []
    for index, category in enumerate((underwear, swimwear)):
        product = Product.objects.create(slug=f"item-{index}", model_name=f"Item {index}",
                                         brand=brand, category=category)
        ProductVariant.objects.create(product=product, sku=f"SKU-{index}", color_code="black",
                                      color_name_key="Black", size="M", price=Decimal("20.00"), demo_quantity=2)
        products.append(product)
    return products


def listing(params=""):
    request = RequestFactory().get(reverse("catalog:list") + "?" + params)
    view = CatalogPageView()
    view.setup(request)
    view.template_name = "catalog/list.html"
    return view.get_context_data()["catalog_listing"]


def test_merchandising_fields_default_to_no_claims():
    category = Category.objects.create(slug="other", name_key="Other")
    brand = Brand.objects.create(slug="other", name="Other")
    product = Product.objects.create(slug="other", model_name="Other", brand=brand, category=category)
    variant = ProductVariant.objects.create(product=product, sku="OTHER", color_code="black",
                                           color_name_key="Black", size="M", price=10)
    assert category.section == "other"
    assert product.new_until is None
    assert variant.is_on_sale is False
    assert listing("new=1")["total"] == 0
    assert listing("sale=1")["total"] == 0


def test_new_until_uses_inclusive_local_date(sections, monkeypatch):
    today = date(2026, 10, 20)
    monkeypatch.setattr(timezone, "localdate", lambda: today)
    for new_until, expected in ((today - timedelta(days=1), 0), (today, 1), (today + timedelta(days=1), 1), (None, 0)):
        Product.objects.filter(pk=sections[0].pk).update(new_until=new_until)
        assert listing("new=1")["total"] == expected


def test_sections_and_sales_apply_on_the_same_variant(sections):
    product = sections[0]
    ProductVariant.objects.create(product=product, sku="SALE-BLUE-L", color_code="blue", color_name_key="Blue",
                                  size="L", price=50, demo_quantity=0, is_on_sale=True)
    assert listing("section=underwear")["products"][0]["slug"] == product.slug
    assert listing("section=swimwear")["products"][0]["slug"] == sections[1].slug
    assert listing("section=other")["total"] == 0
    for params in ("sale=1&color=black", "sale=1&size=M", "sale=1&max_price=20", "sale=1&in_stock=1"):
        assert listing(params)["total"] == 0
    card = listing("sale=1&color=blue&size=L&q=Item&section=underwear")["products"][0]
    assert card["default_color"] == "blue" and card["default_size"] == "L"
    assert card["price"] == Decimal("50.00")


def test_new_filters_survive_pagination_and_individual_chip_removal(sections):
    product = sections[0]
    Product.objects.filter(pk=product.pk).update(new_until=timezone.localdate())
    product.variants.update(is_on_sale=True)
    for index in range(13):
        item = Product.objects.create(slug=f"extra-{index}", model_name=f"Item {index + 2}", brand=product.brand,
                                      category=product.category, new_until=timezone.localdate())
        ProductVariant.objects.create(product=item, sku=f"EXTRA-{index}", color_code="black",
                                      color_name_key="Black", size="M", price=20, is_on_sale=True)
    context = listing("section=underwear&new=1&sale=1&q=Item")
    assert context["total"] == 14
    assert parse_qs(urlparse(context["next_url"]).query) == {
        "section": ["underwear"], "new": ["1"], "sale": ["1"], "q": ["Item"], "page": ["2"],
    }
    chip = next(chip for chip in context["active_filters"] if chip["value"] == "underwear")
    assert parse_qs(urlparse(chip["remove_url"]).query) == {"new": ["1"], "sale": ["1"], "q": ["Item"]}


def test_new_filter_input_validation_is_bounded():
    request = ListingRequest.from_query(QueryDict("section=unknown&new=maybe&sale=2"))
    assert request.errors
    assert not request.filters
    assert ListingRequest.from_query(QueryDict("section=underwear&new=true&sale=on")).filters == {
        "section": "underwear", "new": "1", "sale": "1",
    }


def test_brand_directory_contains_only_active_visible_brands_and_is_paginated(sections, client):
    for index in range(25):
        brand = Brand.objects.create(slug=f"brand-{index:02}", name=f"Brand {index:02}")
        product = Product.objects.create(slug=f"brand-{index:02}", model_name="Model", brand=brand,
                                         category=sections[0].category)
        ProductVariant.objects.create(product=product, sku=f"BRAND-{index}", color_code="black",
                                      color_name_key="Black", size="M", price=20)
    hidden = Brand.objects.create(slug="hidden", name="Hidden")
    product = Product.objects.create(slug="hidden", model_name="Hidden", brand=hidden, category=sections[0].category)
    ProductVariant.objects.create(product=product, sku="HIDDEN", color_code="black", color_name_key="Black",
                                  size="M", price=20, currency="USD")
    response = client.get(reverse("catalog:brands"))
    assert response.status_code == 200
    assert response.context["brand_page"].paginator.count == 26
    assert len(response.context["brand_links"]) == 24
    assert all("brand=" in row["url"] and row["name"] != "Hidden" for row in response.context["brand_links"])
    assert client.get(response.context["next_url"]).context["brand_page"].number == 2
    assert client.post(reverse("catalog:brands")).status_code == 405


def test_staff_can_save_new_until_without_changing_prices(sections, django_user_model, client):
    user = django_user_model.objects.create_user(username="section-editor", is_staff=True)
    user.user_permissions.add(Permission.objects.get(content_type__app_label="catalog", codename="change_product"))
    client.force_login(user)
    product = sections[0]
    data = {"brand": product.brand_id, "category": product.category_id, "model_name": product.model_name,
            "slug": product.slug, "new_until": "2026-12-31",
            "original_state": ProductForm(instance=product).initial["original_state"]}
    response = client.post(reverse("staff:product_edit", kwargs={"pk": product.pk}), data)
    assert response.status_code == 302
    product.refresh_from_db()
    assert product.new_until == date(2026, 12, 31)
    assert product.variants.get().price == Decimal("20.00")
    # New merchandising date participates in optimistic concurrency protection.
    assert client.post(reverse("staff:product_edit", kwargs={"pk": product.pk}), data).status_code == 400


def test_sale_flag_participates_in_variant_edit_and_stale_protection(sections, django_user_model, client):
    user = django_user_model.objects.create_user(username="sale-editor", is_staff=True)
    user.user_permissions.add(*Permission.objects.filter(content_type__app_label="catalog",
                                                        codename__in=["change_product", "change_productvariant"]))
    client.force_login(user)
    product = sections[0]
    url = reverse("staff:variants", kwargs={"pk": product.pk})
    response = client.get(url)
    rows = response.context["formset"].initial
    data = {"fingerprint": response.context["fingerprint"], "variants-TOTAL_FORMS": "1",
            "variants-INITIAL_FORMS": "1", "variants-MAX_NUM_FORMS": "100"}
    for name, value in rows[0].items():
        if value is not False:
            data[f"variants-0-{name}"] = str(value)
    data["variants-0-is_on_sale"] = "on"
    assert client.post(url, data).status_code == 302
    variant = product.variants.get()
    assert variant.is_on_sale is True and variant.price == Decimal("20.00") and variant.demo_quantity == 2
    assert client.post(url, data).status_code == 409


def test_seed_category_data_migration_is_narrow_reversible_and_leaves_money_untouched(sections):
    import importlib
    from types import SimpleNamespace

    from django.apps import apps
    from django.db import connection

    migration = importlib.import_module("web.catalog.migrations.0003_storefront_sections_merchandising")
    known = Category.objects.create(slug="boxershorts", name_key="Boxers")
    manual = Category.objects.create(slug="bodies", name_key="Bodies", section="swimwear")
    before = list(ProductVariant.objects.values_list("pk", "price", "demo_quantity", "is_on_sale"))
    editor = SimpleNamespace(connection=connection)
    migration.classify_seed_categories(apps, editor)
    known.refresh_from_db()
    manual.refresh_from_db()
    assert known.section == "underwear"
    assert manual.section == "swimwear"
    assert Category.objects.get(pk=sections[0].category_id).section == "underwear"
    migration.undo_seed_classification(apps, editor)
    known.refresh_from_db()
    manual.refresh_from_db()
    assert known.section == "other" and manual.section == "swimwear"
    assert list(ProductVariant.objects.values_list("pk", "price", "demo_quantity", "is_on_sale")) == before


def test_combined_merchandising_keeps_fixed_query_budget(sections, django_assert_num_queries):
    product = sections[0]
    Product.objects.filter(pk=product.pk).update(new_until=timezone.localdate())
    product.variants.update(is_on_sale=True)
    for index in range(14):
        item = Product.objects.create(slug=f"budget-{index}", model_name=f"Budget {index}", brand=product.brand,
                                      category=product.category, new_until=timezone.localdate())
        ProductVariant.objects.create(product=item, sku=f"BUDGET-{index}", color_code="black",
                                      color_name_key="Black", size="M", price=20, is_on_sale=True)
    with django_assert_num_queries(10):
        result = listing("section=underwear&new=1&sale=1")
        assert len(result["products"]) == 12
    with django_assert_num_queries(10):
        result = listing("section=underwear&new=1&sale=1&q=SKU-0")
        assert len(result["products"]) == 1


def test_brands_directory_query_budget_is_two_without_per_brand_sql(sections, django_assert_num_queries):
    from web.catalog.brand_directory_view import BrandDirectoryView

    request = RequestFactory().get(reverse("catalog:brands"))
    view = BrandDirectoryView()
    view.setup(request)
    with django_assert_num_queries(2):
        context = view.get_context_data()
        assert len(context["brand_links"]) == 1
        assert context["brand_links"][0]["name"] == "Brand"
