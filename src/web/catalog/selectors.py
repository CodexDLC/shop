from django.db.models import Exists, OuterRef, Prefetch, Q

from .models import Product, ProductVariant


def storefront_products():
    """Lazy queryset: callers must bound the page before evaluation (four SQL queries)."""
    return Product.objects.filter(is_active=True).select_related("brand", "category").prefetch_related(
        Prefetch("variants", queryset=ProductVariant.objects.filter(is_active=True)), "images", "tags"
    )


def catalog_products(*, query="", category="", brand="", tag="", limit=24, offset=0):
    """Bounded, lazy catalogue page; slug filters combine with a literal text search.

    Search covers model name, brand name, tag slugs and active variant SKUs.
    Translation keys are identifiers rather than searchable customer-facing text.
    Empty criteria are ignored; unknown slugs return an empty page. Sold-out active
    variants remain visible, but inactive variants cannot match or be presented.
    Related data costs four queries for a nonempty page, regardless of page size.
    """
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer between 1 and 100")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be a nonnegative integer")

    products = storefront_products()
    if category.strip():
        products = products.filter(category__slug=category.strip())
    if brand.strip():
        products = products.filter(brand__slug=brand.strip())
    if tag.strip():
        tag_match = Product.tags.through.objects.filter(
            product_id=OuterRef("pk"), tag__slug=tag.strip(),
        )
        products = products.filter(Exists(tag_match))

    term = query.strip()
    if term:
        matching_skus = ProductVariant.objects.filter(
            product_id=OuterRef("pk"), is_active=True, sku__icontains=term,
        )
        matching_tags = Product.tags.through.objects.filter(
            product_id=OuterRef("pk"), tag__slug__icontains=term,
        )
        products = products.filter(
            Q(model_name__icontains=term) | Q(brand__name__icontains=term)
            | Q(Exists(matching_skus)) | Q(Exists(matching_tags))
        )
    return products.order_by("pk")[offset:offset + limit]


def gallery_for_color(product, color_code):
    """Use the prefetched relation; no per-size duplication or filtered-manager query."""
    images = list(product.images.all())
    return [image for image in images if image.color_code == color_code] or [
        image for image in images if not image.color_code
    ]
