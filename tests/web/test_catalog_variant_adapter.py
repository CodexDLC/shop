import pytest
from django.core.management import call_command

from codex_ecommerce.catalog import CatalogSelectionError
from web.catalog.adapters import CatalogVariantSelection
from web.catalog.models import Product, ProductVariant

pytestmark = pytest.mark.django_db


def test_adapter_returns_exact_variant_with_three_queries_and_no_writes(django_assert_num_queries):
    call_command("seed_demo_catalog")
    variant = ProductVariant.objects.filter(product__slug="manstore-m2223", size="M").first()
    before = ProductVariant.objects.count()
    with django_assert_num_queries(3):
        result = CatalogVariantSelection().select(
            product_slug="manstore-m2223", color=variant.color_code, size="M",
        )
    assert result.variant.sku == variant.sku
    assert result.variant.price == variant.price
    assert result.purchase_allowed is True  # demo availability, never checkout authorization
    assert ProductVariant.objects.count() == before


@pytest.mark.parametrize("inactive", [False, True])
def test_adapter_never_substitutes_an_unavailable_variant(inactive):
    call_command("seed_demo_catalog")
    variant = ProductVariant.objects.filter(product__slug="manstore-m2223", size="M").first()
    variant.is_active = not inactive
    variant.demo_quantity = 0
    variant.save()
    result = CatalogVariantSelection().select(
        product_slug="manstore-m2223", color=variant.color_code, size="M",
    )
    assert result.variant.sku == variant.sku
    assert result.purchase_allowed is False


def test_adapter_unknown_size_is_domain_error():
    call_command("seed_demo_catalog")
    with pytest.raises(CatalogSelectionError) as error:
        CatalogVariantSelection().select(product_slug="manstore-m2223", color="black", size="XXXL")
    assert error.value.code == "catalog.variant_not_found"


def test_inactive_product_is_not_exposed():
    call_command("seed_demo_catalog")
    Product.objects.filter(slug="manstore-m2223").update(is_active=False)
    with pytest.raises(Product.DoesNotExist):
        CatalogVariantSelection().select(product_slug="manstore-m2223", color="black", size="M")
