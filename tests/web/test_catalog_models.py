from decimal import Decimal

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction

from web.catalog.models import Product, ProductImage, ProductVariant
from web.catalog.selectors import gallery_for_color, storefront_products

pytestmark = pytest.mark.django_db


def test_seed_is_idempotent_and_groups_variants():
    call_command("seed_demo_catalog")
    call_command("seed_demo_catalog")
    assert Product.objects.count() == 4
    assert ProductVariant.objects.count() == 32
    product = Product.objects.get(slug="manstore-m2223")
    assert product.variants.count() == 8
    assert product.images.count() == 1
    assert product.variants.filter(demo_quantity=0).count() == 2


def test_sku_unique_and_negative_price_rejected():
    call_command("seed_demo_catalog")
    variant = ProductVariant.objects.first()
    variant.pk = None
    with pytest.raises(IntegrityError), transaction.atomic():
        variant.save(force_insert=True)
    with pytest.raises(IntegrityError), transaction.atomic():
        ProductVariant.objects.filter(pk=ProductVariant.objects.first().pk).update(price=Decimal("-1"))


def test_color_gallery_shared_by_sizes_and_falls_back():
    call_command("seed_demo_catalog")
    product = Product.objects.first()
    specific = ProductImage.objects.create(
        product=product, color_code="black", position=0,
        image_url="https://example.test/black.jpg", alt_key="catalog.photo.black",
    )
    assert gallery_for_color(product, "black") == [specific]
    assert gallery_for_color(product, "navy")[0].color_code == ""


@pytest.mark.parametrize("limit", [1, 4])
def test_storefront_relations_have_fixed_query_budget(django_assert_num_queries, limit):
    call_command("seed_demo_catalog")
    with django_assert_num_queries(4):
        products = list(storefront_products()[:limit])
        for product in products:
            assert product.brand.name
            assert product.category.name_key
            assert list(product.tags.all())
            assert list(product.variants.all())
            assert gallery_for_color(product, "black")
