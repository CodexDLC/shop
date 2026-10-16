from collections.abc import Iterable

from .error import CatalogSelectionError
from .gallery import Gallery
from .selection import VariantSelection
from .variant import Variant


class VariantSelector:
    """Select within one product snapshot; no implicit size or colour substitutions."""

    def select(
        self, variants: Iterable[Variant], galleries: Iterable[Gallery], *, color: str, size: str
    ) -> VariantSelection:
        variants = tuple(variants)
        galleries = tuple(galleries)
        identities = [(variant.color, variant.size) for variant in variants]
        skus = [variant.sku for variant in variants]
        gallery_colors = [gallery.color for gallery in galleries]
        if len(set(identities)) != len(identities) or len(set(skus)) != len(skus):
            raise CatalogSelectionError("catalog.ambiguous_variants", "contact_support")
        if len(set(gallery_colors)) != len(gallery_colors):
            raise CatalogSelectionError("catalog.ambiguous_galleries", "contact_support")
        if len({variant.currency for variant in variants}) > 1:
            raise CatalogSelectionError("catalog.currency_mismatch", "contact_support")
        selected = next((variant for variant in variants if variant.color == color and variant.size == size), None)
        if selected is None:
            raise CatalogSelectionError("catalog.variant_not_found", "choose_variant")
        gallery = next((gallery for gallery in galleries if gallery.color == color and gallery.images), None)
        if gallery is None:
            gallery = next((gallery for gallery in galleries if gallery.color is None), Gallery(None, ()))
        return VariantSelection(variant=selected, gallery=gallery)
