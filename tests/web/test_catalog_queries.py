from decimal import Decimal

import pytest
from django.core.management import call_command

from web.catalog.models import Product, ProductVariant, Tag
from web.catalog.selectors import catalog_products, gallery_for_color

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded_catalog():
    call_command("seed_demo_catalog")
    return list(Product.objects.select_related("brand", "category").order_by("pk"))


def test_search_filters_combine_and_unknown_values_are_empty(seeded_catalog):
    product = seeded_catalog[0]
    tag = Tag.objects.create(slug="featured-choice", label_key="tags.featured")
    product.tags.add(tag)
    assert [p.pk for p in catalog_products(
        query=product.model_name.lower(), category=product.category.slug,
        brand=product.brand.slug, tag=tag.slug,
    )] == [product.pk]
    for field in ("category", "brand", "tag"):
        assert list(catalog_products(**{field: "unknown-slug"})) == []
    assert list(catalog_products(query="not-a-real-product")) == []


def test_search_matches_brand_sku_and_tag_without_m2m_duplicates(seeded_catalog):
    product = seeded_catalog[0]
    for slug in ("special-style", "special-material"):
        product.tags.add(Tag.objects.create(slug=slug, label_key=f"tags.{slug}"))
    variant = product.variants.first()
    assert [p.pk for p in catalog_products(query=variant.sku.lower())] == [product.pk]
    assert [p.pk for p in catalog_products(query="special")] == [product.pk]
    expected = [p.pk for p in seeded_catalog if p.brand_id == product.brand_id]
    assert [p.pk for p in catalog_products(query=product.brand.name.lower())] == expected


def test_inactive_products_and_variants_are_excluded_without_hiding_sold_out(seeded_catalog):
    product, inactive = seeded_catalog[:2]
    inactive.is_active = False
    inactive.save(update_fields=["is_active"])
    variant = product.variants.first()
    variant.sku = "hidden-only-sku"
    variant.is_active = False
    variant.save(update_fields=["sku", "is_active"])
    assert list(catalog_products(query="hidden-only-sku")) == []
    results = list(catalog_products())
    assert inactive.pk not in [p.pk for p in results]
    visible = next(p for p in results if p.pk == product.pk)
    assert all(v.is_active for v in visible.variants.all())
    assert any(v.demo_quantity == 0 for v in visible.variants.all())


def test_search_is_literal_and_does_not_search_translation_keys(seeded_catalog):
    product = seeded_catalog[0]
    product.model_name = "Style 100%_Cotton"
    product.description_key = "secret.translation.identifier"
    product.save(update_fields=["model_name", "description_key"])
    assert [p.pk for p in catalog_products(query="%_")] == [product.pk]
    assert list(catalog_products(query="secret.translation.identifier")) == []


def test_page_is_bounded_stable_and_whitespace_criteria_are_ignored(seeded_catalog):
    expected = [p.pk for p in seeded_catalog]
    assert [p.pk for p in catalog_products(limit=2, offset=1)] == expected[1:3]
    assert [p.pk for p in catalog_products(query=" ", brand=" ", category=" ", tag=" ")] == expected
    assert list(catalog_products(offset=100)) == []


@pytest.mark.parametrize("limit", [0, -1, 101, None, True, "24"])
def test_invalid_page_limit_is_rejected(limit):
    with pytest.raises(ValueError, match="limit"):
        catalog_products(limit=limit)


@pytest.mark.parametrize("offset", [-1, None, True, "0"])
def test_invalid_page_offset_is_rejected(offset):
    with pytest.raises(ValueError, match="offset"):
        catalog_products(offset=offset)


@pytest.mark.parametrize("size", [1, 4, 20])
def test_query_budget_does_not_grow_with_cards(seeded_catalog, django_assert_num_queries, size):
    original = seeded_catalog[0]
    for index in range(16):
        product = Product.objects.create(
            slug=f"additional-{index}", model_name=f"Additional {index}",
            brand=original.brand, category=original.category,
        )
        ProductVariant.objects.create(
            product=product, sku=f"ADDITIONAL-{index}", color_code="black",
            color_name_key="colors.black", size="M", price=Decimal("20.00"),
        )
    with django_assert_num_queries(0):
        page = catalog_products(limit=size, brand=original.brand.slug)
    with django_assert_num_queries(4):
        for product in page:
            assert product.brand.name
            assert product.category.name_key
            list(product.variants.all())
            list(product.tags.all())
            gallery_for_color(product, "black")
