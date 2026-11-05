from collections import defaultdict

from django.db.models import Prefetch

from codex_ecommerce.catalog import Gallery, Variant, VariantSelector
from web.catalog.category_visibility import visible_category_ids
from web.catalog.models import Product, ProductVariant
from web.inventory.availability import InventoryAvailability
from web.inventory.availability_queries import with_availability


class CatalogVariantSelection:
    """Read-only availability snapshot; does not reserve stock or authorize checkout."""

    def select(self, *, product_slug, color, size):
        product = Product.objects.filter(is_active=True, category_id__in=visible_category_ids()).prefetch_related(
            Prefetch('variants', queryset=with_availability(ProductVariant.objects.all())), "images",
        ).get(slug=product_slug)
        return self.select_snapshot(product, color=color, size=size)

    def select_snapshot(self, product, *, color, size):
        variants = tuple(
            Variant(
                sku=row.sku, color=row.color_code, size=row.size,
                price=row.price, currency=row.currency,
                available=InventoryAvailability.from_variant(row).available, active=row.is_active,
            )
            for row in product.variants.all()
        )
        galleries = defaultdict(list)
        for row in product.images.all():
            galleries[row.color_code or None].append(row.public_url)
        return VariantSelector().select(
            variants,
            tuple(Gallery(color=code, images=tuple(images)) for code, images in galleries.items()),
            color=color, size=size,
        )
