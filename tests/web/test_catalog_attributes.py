from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.http import QueryDict
from django.utils import timezone

from web.catalog.listing_request import ListingRequest
from web.catalog.models import (
    Brand,
    Category,
    Material,
    Product,
    ProductProperty,
    ProductReview,
    ProductVariant,
    Tag,
)
from web.catalog.selectors import listing_facets, listing_products, storefront_products

pytestmark = pytest.mark.django_db


@pytest.fixture
def catalog():
    brand = Brand.objects.create(slug="attributes-brand", name="Attributes Brand")
    category = Category.objects.create(slug="attributes-category", name_key="category", section="underwear")
    products = []
    for index in range(5):
        product = Product.objects.create(
            slug=f"attributes-{index}", model_name=f"Model {index}", brand=brand, category=category,
        )
        ProductVariant.objects.create(
            product=product, sku=f"ATTR-{index}", color_code="black", color_name_key="black",
            size="M", price=10 + index, demo_quantity=2,
        )
        products.append(product)
    return products


def selected(params=""):
    return listing_products(ListingRequest.from_query(QueryDict(params)))


def ids(params=""):
    return list(selected(params).values_list("pk", flat=True))


@pytest.mark.parametrize("model", [Material, ProductProperty])
def test_dictionary_constraints_and_plain_names(model):
    entry = model.objects.create(slug="cotton", name="<Cotton & material>")
    assert str(entry) == "<Cotton & material>"
    with pytest.raises(ValidationError):
        model(slug="cotton", name="Duplicate").full_clean()
    with pytest.raises(ValidationError):
        model(slug="a" * 121, name="Too long slug").full_clean()
    with pytest.raises(ValidationError):
        model(slug="other", name="a" * 161).full_clean()


def test_existing_product_keeps_unknown_publication_date(catalog):
    for product in catalog:
        product.refresh_from_db()
        assert product.published_at is None
        assert not product.materials.exists()
        assert not product.properties.exists()
    field = Product._meta.get_field("published_at")
    assert field.null and field.blank and field.db_index and not field.has_default()
    assert not field.auto_now and not field.auto_now_add


@pytest.mark.parametrize("key", ["material", "property"])
def test_attribute_parser_bounds_and_deduplicates(key):
    parsed = ListingRequest.from_query(QueryDict(f"{key}=cotton&{key}=%20cotton%20&{key}="))
    assert parsed.filters[key] == ["cotton"]
    assert not parsed.errors
    params = "&".join(f"{key}=value-{index}" for index in range(25))
    parsed = ListingRequest.from_query(QueryDict(params))
    assert len(parsed.filters[key]) == 20
    assert parsed.errors == ("catalog.listing.error.invalid_filter",)
    parsed = ListingRequest.from_query(QueryDict(f"{key}=" + "x" * 121))
    assert key not in parsed.filters
    assert parsed.errors
    assert ListingRequest.from_query(QueryDict(f"{key}=" + "x" * 120)).filters[key] == ["x" * 120]


@pytest.mark.parametrize("sort", ["newest", "rating"])
def test_supported_sorts_and_unsupported_popularity(sort):
    assert ListingRequest.from_query(QueryDict(f"sort={sort}")).sort == sort
    parsed = ListingRequest.from_query(QueryDict("sort=popular"))
    assert parsed.sort == "name"
    assert parsed.errors == ("catalog.listing.error.invalid_sort",)


def test_filter_or_within_and_between_without_join_duplicates(catalog):
    cotton = Material.objects.create(slug="cotton", name="Cotton")
    linen = Material.objects.create(slug="linen", name="Linen")
    soft = ProductProperty.objects.create(slug="soft", name="Soft")
    light = ProductProperty.objects.create(slug="light", name="Light")
    catalog[0].materials.add(cotton, linen)
    catalog[0].properties.add(soft, light)
    catalog[1].materials.add(linen)
    catalog[1].properties.add(light)
    catalog[2].materials.add(cotton)
    catalog[0].new_until = timezone.localdate()
    catalog[0].save(update_fields=["new_until"])
    catalog[0].variants.update(is_on_sale=True)
    catalog[0].tags.add(Tag.objects.create(slug="essential", label_key="Essential"))
    assert ids("material=cotton&material=linen&property=soft&property=light") == [
        catalog[0].pk, catalog[1].pk,
    ]
    assert ids("material=linen&property=soft") == [catalog[0].pk]
    assert ids("material=missing") == []
    assert ids("property=missing") == []
    assert ids("material=cotton&material=cotton&property=soft&q=Model&section=underwear"
               "&brand=attributes-brand&category=attributes-category&size=M&color=black"
               "&min_price=10&max_price=10&in_stock=1&tag=essential&new=1&sale=1") == [catalog[0].pk]
    ProductVariant.objects.create(product=catalog[0], sku="BLUE-L", color_code="blue",
                                  color_name_key="blue", size="L", price=100, demo_quantity=0)
    assert ids("material=cotton&property=soft&color=blue&size=M") == []
    assert ids("material=cotton&property=soft&color=blue&max_price=20") == []
    assert ids("material=cotton&property=soft&color=blue&in_stock=1") == []


def test_attributes_cannot_expose_inactive_or_non_eur_products(catalog):
    material = Material.objects.create(slug="cotton", name="Cotton")
    prop = ProductProperty.objects.create(slug="soft", name="Soft")
    for product in catalog:
        product.materials.add(material)
        product.properties.add(prop)
    catalog[0].variants.update(is_active=False)
    catalog[1].variants.update(currency="USD")
    catalog[2].is_active = False
    catalog[2].save(update_fields=["is_active"])
    assert ids("material=cotton&property=soft") == [catalog[3].pk, catalog[4].pk]


def test_newest_known_dates_before_unknown_stable_name_pk(catalog):
    now = timezone.now()
    for index, published_at in ((0, now - timedelta(days=1)), (1, now), (2, now)):
        catalog[index].published_at = published_at
        catalog[index].save(update_fields=["published_at"])
    catalog[2].model_name = catalog[1].model_name
    catalog[2].save(update_fields=["model_name"])
    assert ids("sort=newest") == [catalog[i].pk for i in (1, 2, 0, 3, 4)]


def test_rating_approved_average_and_count_null_last_stable(catalog, django_assert_num_queries):
    for product, ratings in ((catalog[0], [4, 4]), (catalog[1], [5]), (catalog[2], [4])):
        for rating in ratings:
            ProductReview.objects.create(product=product, rating=rating, status="approved")
    for status in ("pending", "rejected"):
        ProductReview.objects.create(product=catalog[1], rating=1, status=status)
        ProductReview.objects.create(product=catalog[3], rating=5, status=status)
    catalog[4].model_name = catalog[3].model_name
    catalog[4].save(update_fields=["model_name"])
    with django_assert_num_queries(1):
        assert ids("sort=rating") == [catalog[i].pk for i in (1, 0, 2, 3, 4)]


def test_facets_only_visible_products_with_plain_names_and_seven_queries(catalog, django_assert_num_queries):
    for index, product in enumerate(catalog):
        material = Material.objects.create(slug=f"material-{index}", name=f"Material {index}")
        prop = ProductProperty.objects.create(slug=f"property-{index}", name=f"Property {index}")
        product.materials.add(material)
        product.properties.add(prop)
    catalog[0].is_active = False
    catalog[0].save(update_fields=["is_active"])
    catalog[1].variants.update(is_active=False)
    catalog[2].variants.update(currency="USD")
    Material.objects.create(slug="unused", name="Unused")
    with django_assert_num_queries(7):
        facets = listing_facets()
    assert facets["materials"] == [("material-3", "Material 3"), ("material-4", "Material 4")]
    assert facets["properties"] == [("property-3", "Property 3"), ("property-4", "Property 4")]


def test_attribute_facets_are_capped_and_ordered(catalog):
    for model, relation in ((Material, "materials"), (ProductProperty, "properties")):
        entries = model.objects.bulk_create([
            model(slug=f"value-{index:03}", name=f"Name {index:03}") for index in range(205)
        ])
        getattr(catalog[0], relation).add(*entries)
    facets = listing_facets()
    for key in ("materials", "properties"):
        assert len(facets[key]) == 200
        assert facets[key][0] == ("value-000", "Name 000")
        assert facets[key][-1] == ("value-199", "Name 199")


def test_new_sort_and_attributes_keep_selector_queries_constant(catalog, django_assert_num_queries):
    material = Material.objects.create(slug="cotton", name="Cotton")
    for product in catalog:
        product.materials.add(material)
    for sort in ("newest", "rating"):
        with django_assert_num_queries(4):
            rows = list(selected(f"sort={sort}&material=cotton"))
            for row in rows:
                assert not hasattr(row, "approved_rating")
                assert not hasattr(row, "approved_review_count")
                list(row.variants.all())
                list(row.tags.all())
                list(row.images.all())
    with django_assert_num_queries(4):
        list(storefront_products())
