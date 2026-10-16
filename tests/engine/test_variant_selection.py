from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from codex_ecommerce.catalog import CatalogSelectionError, Gallery, Variant, VariantSelector


def variant(**changes):
    return replace(Variant("black-m", "black", "M", Decimal("29.95"), "EUR", True), **changes)


def test_exact_variant_and_color_gallery_selection():
    variants = (variant(), variant(sku="black-l", size="L"), variant(sku="navy-m", color="navy"))
    galleries = (Gallery(None, ("general",)), Gallery("navy", ("navy-front", "navy-back")))
    selected = VariantSelector().select(variants, galleries, color="navy", size="M")
    assert selected.variant.sku == "navy-m"
    assert selected.gallery.images == ("navy-front", "navy-back")
    assert selected.variant.price == Decimal("29.95")
    assert selected.purchase_allowed
    assert VariantSelector().select(variants, galleries, color="black", size="L").variant.sku == "black-l"


def test_gallery_never_uses_other_color_and_sizes_share_gallery():
    variants = (variant(), variant(sku="black-l", size="L"))
    galleries = (Gallery("navy", ("navy-front",)), Gallery(None, ("general",)))
    for size in ("M", "L"):
        assert VariantSelector().select(variants, galleries, color="black", size=size).gallery.images == ("general",)
    assert VariantSelector().select(variants, galleries[:1], color="black", size="M").gallery.images == ()


def test_empty_color_gallery_falls_back_to_general():
    selected = VariantSelector().select(
        (variant(),), (Gallery("black", ()), Gallery(None, ("general",))), color="black", size="M"
    )
    assert selected.gallery.images == ("general",)


@pytest.mark.parametrize("changes", [{"available": False}, {"active": False}, {"active": False, "available": False}])
def test_unavailable_or_inactive_variant_stays_visible_but_not_purchasable(changes):
    selected = VariantSelector().select((variant(**changes),), (), color="black", size="M")
    assert selected.variant.sku == "black-m"
    assert not selected.purchase_allowed


@pytest.mark.parametrize("color,size", [("black", "XL"), ("navy", "M"), ("BLACK", "M")])
def test_missing_selection_has_stable_error_and_no_fallback(color, size):
    with pytest.raises(CatalogSelectionError) as caught:
        VariantSelector().select((variant(),), (), color=color, size=size)
    assert caught.value.code == "catalog.variant_not_found"
    assert caught.value.action == "choose_variant"


@pytest.mark.parametrize("second", [variant(sku="duplicate"), variant(color="navy")])
def test_duplicate_color_size_or_sku_is_rejected(second):
    with pytest.raises(CatalogSelectionError, match="catalog.ambiguous_variants"):
        VariantSelector().select((variant(), second), (), color="black", size="M")


def test_mixed_currencies_are_not_silently_selected():
    with pytest.raises(CatalogSelectionError, match="catalog.currency_mismatch"):
        VariantSelector().select((variant(), variant(sku="navy", color="navy", currency="USD")), (), color="black", size="M")


def test_duplicate_gallery_is_rejected():
    with pytest.raises(CatalogSelectionError, match="catalog.ambiguous_galleries"):
        VariantSelector().select((variant(),), (Gallery(None, ("a",)), Gallery(None, ("b",))), color="black", size="M")


def test_dtos_are_immutable():
    selected = VariantSelector().select((variant(),), (Gallery(None, ("a",)),), color="black", size="M")
    for target, field, value in ((selected, "variant", variant()), (selected.variant, "sku", "changed"),
                                 (selected.gallery, "images", ("changed",))):
        with pytest.raises(FrozenInstanceError):
            setattr(target, field, value)


@pytest.mark.parametrize("price", [1.2, Decimal("NaN"), Decimal("Infinity"), Decimal("-1")])
def test_invalid_money_rejected(price):
    with pytest.raises(ValueError):
        variant(price=price)


def test_gallery_rejects_mutable_image_collection():
    with pytest.raises(ValueError):
        Gallery(None, ["image"])
