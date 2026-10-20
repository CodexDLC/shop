from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest
from django.http import QueryDict
from django.test import RequestFactory
from django.urls import reverse

from web.catalog.listing_request import ListingRequest
from web.catalog.models import Brand, Category, Product, ProductVariant, Tag
from web.catalog.selectors import listing_products
from web.catalog.views import CatalogPageView

pytestmark = pytest.mark.django_db


@pytest.fixture
def items():
    brand = Brand.objects.create(slug="test-brand", name="Test Brand")
    category = Category.objects.create(slug="test-category", name_key="test.category")
    rows = []
    for index in range(15):
        product = Product.objects.create(
            slug=f"model-{index}", model_name=f"Model {index:02}", brand=brand, category=category,
        )
        ProductVariant.objects.create(
            product=product, sku=f"SKU-{index}", color_code="black", color_name_key="black",
            size="M", price=Decimal(index + 10), demo_quantity=2,
        )
        rows.append(product)
    return rows


def listing_context(params="", route="catalog:list"):
    request = RequestFactory().get(reverse(route) + ("?" + params if params else ""))
    view = CatalogPageView()
    view.setup(request)
    view.template_name = "catalog/list.html"
    return view.get_context_data()


def test_listing_is_paginated_and_preserves_repeated_filters(items):
    result = listing_context("brand=test-brand&brand=other&q=Model&size=M&sort=price_desc")
    listing = result["catalog_listing"]
    assert listing["total"] == 15
    assert len(listing["products"]) == 12
    assert listing["products"][0]["slug"] == "model-14"
    assert result["listing_page"] is True
    query = parse_qs(urlparse(listing["next_url"]).query)
    assert query["brand"] == ["test-brand", "other"]
    assert query["q"] == ["Model"]
    assert query["page"] == ["2"]
    assert listing["page_start"] == 1
    assert listing["page_end"] == 12


def test_same_active_variant_must_match_all_filters(items):
    product = items[0]
    ProductVariant.objects.create(
        product=product, sku="BLUE-L", color_code="blue", color_name_key="blue", size="L",
        price=Decimal("99.00"), demo_quantity=0,
    )
    for params in ("color=blue&size=M", "color=blue&in_stock=1", "color=blue&max_price=20"):
        assert listing_context(params)["catalog_listing"]["total"] == 0
    result = listing_context("color=blue&size=L&min_price=99&max_price=99")["catalog_listing"]
    assert result["total"] == 1
    assert result["products"][0]["default_color"] == "blue"
    assert result["products"][0]["default_size"] == "L"
    assert str(result["products"][0]["price"]) == "99.00"


def test_inactive_and_non_eur_variants_never_match(items):
    items[0].variants.update(is_active=False)
    items[1].variants.update(currency="USD")
    items[2].is_active = False
    items[2].save(update_fields=["is_active"])
    assert listing_context()["catalog_listing"]["total"] == 12
    assert listing_context("q=SKU-0")["catalog_listing"]["total"] == 0


def test_unknown_and_empty_routes_use_real_results(items):
    assert listing_context("brand=missing")["catalog_listing"]["total"] == 0
    for route in ("catalog:empty", "catalog:search", "catalog:search_empty", "catalog:mobile"):
        assert listing_context(route=route)["catalog_listing"]["total"] == 15


def test_request_validation_bounds_and_bad_pages_are_safe(items):
    for params in ("min_price=NaN", "max_price=Infinity", "min_price=-1", "min_price=5&max_price=2"):
        result = listing_context(params)["catalog_listing"]
        assert result["errors"]
        assert result["total"] == 15
    for page in ("0", "-1", "bad", "9999999999999999999999"):
        assert 1 <= listing_context(f"page={page}")["catalog_listing"]["page"] <= 2
    parsed = ListingRequest.from_query(QueryDict("q=" + "x" * 500))
    assert len(parsed.query) <= 160
    assert parsed.errors


def test_tag_search_has_no_duplicates_and_query_budget_is_constant(items, django_assert_num_queries):
    for slug in ("cotton-one", "cotton-two"):
        tag = Tag.objects.create(slug=slug, label_key=slug)
        items[0].tags.add(tag)
    request = ListingRequest.from_query(QueryDict("q=cotton"))
    assert list(listing_products(request).values_list("pk", flat=True)) == [items[0].pk]
    # Count and five bounded facet queries plus four prefetch queries; no per-card SQL.
    with django_assert_num_queries(10):
        result = listing_context()
        assert len(result["catalog_listing"]["products"]) == 12
    with django_assert_num_queries(10):
        result = listing_context("q=Model%2000")
        assert len(result["catalog_listing"]["products"]) == 1


def test_numeric_sort_matches_price_filters_and_cards_only_expose_eur(items):
    product = items[0]
    ProductVariant.objects.create(
        product=product, sku="EUR-PREMIUM", color_code="blue", color_name_key="blue", size="L",
        price=Decimal("100.00"), demo_quantity=1,
    )
    ProductVariant.objects.create(
        product=product, sku="USD-CHEAP", color_code="red", color_name_key="red", size="L",
        price=Decimal("1.00"), currency="USD", demo_quantity=1,
    )
    card = listing_context("min_price=99&sort=price_asc")["catalog_listing"]["products"][0]
    assert card["price"] == Decimal("100.00")
    assert card["default_color"] == "blue"
    assert {variant["currency"] for variant in card["variants"]} == {"EUR"}
    assert "red" not in {color["code"] for color in card["colors"]}


def test_chip_removes_one_multivalue_filter_and_resets_page(items):
    result = listing_context("brand=test-brand&brand=missing&size=M&page=2")["catalog_listing"]
    chip = next(chip for chip in result["active_filters"] if chip["value"] == "missing")
    query = parse_qs(urlparse(chip["remove_url"]).query)
    assert query == {"brand": ["test-brand"], "size": ["M"]}
    assert result["clear_url"] == reverse("catalog:list")


def test_empty_database_has_no_demo_products(client):
    response = client.get(reverse("catalog:list"))
    assert response.status_code == 200
    assert response.context["catalog_listing"]["products"] == []
    assert response.context["catalog_products"] == []
    assert response.context["products"] == {}


def test_listing_get_executes_only_reads(items, client, django_capture_on_commit_callbacks):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as captured:
        response = client.get(reverse("catalog:list"), {"q": "Model", "brand": "test-brand"})
    assert response.status_code == 200
    assert all(not sql["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for sql in captured)


def test_post_is_not_supported(items, client):
    response = client.post(reverse("catalog:list"), {"sku": "SKU-0", "quantity": "2"})
    assert response.status_code == 405
    assert items[0].variants.get().demo_quantity == 2


def test_facets_exclude_inactive_products_and_variants(items):
    hidden_brand = Brand.objects.create(slug="hidden-brand", name="Hidden Brand")
    hidden = Product.objects.create(
        slug="hidden", model_name="Hidden", brand=hidden_brand, category=items[0].category,
    )
    ProductVariant.objects.create(
        product=hidden, sku="HIDDEN", color_code="hidden", color_name_key="Hidden",
        size="Hidden", price=10, is_active=False,
    )
    facets = listing_context()["catalog_listing"]["facets"]
    assert {row["value"] for row in facets["brands"]} == {"test-brand"}
    assert {row["value"] for row in facets["colors"]} == {"black"}
    assert {row["value"] for row in facets["sizes"]} == {"M"}


def test_request_bounds_repeated_filters_and_rejects_precision():
    params = QueryDict("&".join(f"brand=b-{index}" for index in range(50)))
    parsed = ListingRequest.from_query(params)
    assert len(parsed.filters["brand"]) == 20
    assert parsed.errors == ("catalog.listing.error.invalid_filter",)
    assert ListingRequest.from_query(QueryDict("min_price=0.001")).errors
    assert ListingRequest.from_query(QueryDict("sort=popularity")).sort == "name"
    assert ListingRequest.from_query(QueryDict("page=2")).page == 2


def test_selected_unknown_facets_remain_available_to_submit(items):
    listing = listing_context(
        "brand=missing&category=unknown-category&tag=unknown-tag&color=unknown-color&size=unknown-size"
    )["catalog_listing"]
    assert listing["total"] == 0
    for field, value in (("brands", "missing"), ("categories", "unknown-category"),
                         ("tags", "unknown-tag"), ("colors", "unknown-color"), ("sizes", "unknown-size")):
        assert {"value": value, "label": value, "selected": True} in listing["facets"][field]


def test_selected_brand_after_facet_cap_is_preserved(items):
    brands = Brand.objects.bulk_create([
        Brand(slug=f"facet-{index:03}", name=f"Facet {index:03}") for index in range(201)
    ])
    products = Product.objects.bulk_create([
        Product(slug=f"facet-{index:03}", model_name=f"Facet {index:03}",
                brand=brand, category=items[0].category)
        for index, brand in enumerate(brands)
    ])
    ProductVariant.objects.bulk_create([
        ProductVariant(product=product, sku=f"FACET-{index}", color_code="black",
                       color_name_key="black", size="M", price=10)
        for index, product in enumerate(products)
    ])
    listing = listing_context("brand=facet-200")["catalog_listing"]
    assert listing["total"] == 1
    assert any(row["value"] == "facet-200" and row["selected"] for row in listing["facets"]["brands"])
    assert len(listing["facets"]["brands"]) == 201
