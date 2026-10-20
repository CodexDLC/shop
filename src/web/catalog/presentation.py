import re
from collections import defaultdict

from django.urls import reverse

from codex_ecommerce.catalog import Gallery, Variant, VariantSelector
from web.localization import translate_text


def product_presentation(product, *, code, selected_sku=None, currency=None):
    """Project a prefetched ORM snapshot; no queries, writes or invented variants."""
    rows = [row for row in product.variants.all() if row.is_active and (currency is None or row.currency == currency)]
    images = defaultdict(list)
    for image in product.images.all():
        images[image.color_code or None].append(image.image_url)
    colors = {}
    for row in rows:
        colors.setdefault(row.color_code, {
            "code": row.color_code, "label": translate_text(row.color_name_key),
            "hex": row.color_hex if re.fullmatch(r"#[0-9a-fA-F]{6}", row.color_hex) else "#183F30",
        })
    variants = tuple(Variant(
        sku=row.sku, color=row.color_code, size=row.size, price=row.price,
        currency=row.currency, available=row.is_available,
    ) for row in rows)
    # An initial selection is explicit; subsequent changes never substitute size or color.
    default = next((row for row in rows if row.sku == selected_sku), None)
    default = default or next((row for row in rows if row.is_available and row.size == "M"), None)
    default = default or next((row for row in rows if row.is_available), None) or next(iter(rows), None)
    galleries = {color: images.get(color) or images.get(None, []) for color in colors}
    initial_images = images.get(None, [])
    price = None
    if default:
        selected = VariantSelector().select(
            variants, tuple(Gallery(color=color, images=tuple(urls)) for color, urls in images.items()),
            color=default.color_code, size=default.size,
        )
        initial_images = list(selected.gallery.images)
        price = selected.variant.price
    return {
        "id": product.pk, "code": code, "slug": product.slug, "brand": product.brand.name,
        "name": product.model_name, "price": price,
        "description": translate_text(product.description_key) if product.description_key else "",
        "photo_url": initial_images[0] if initial_images else "",
        "detail_url": reverse("catalog:detail", kwargs={"slug": product.slug}),
        "preview_url": reverse("catalog:variant_preview", kwargs={"slug": product.slug}),
        "colors": list(colors.values()), "sizes": list(dict.fromkeys(row.size for row in rows)),
        "variants": [{"color": row.color_code, "size": row.size, "sku": row.sku,
                      "price": str(row.price), "currency": row.currency,
                      "available": row.is_available} for row in rows],
        "galleries": galleries, "default_color": default.color_code if default else "",
        "default_size": default.size if default else "", "is_demo": True,
    }


def selection_texts():
    return {name: translate_text(f"catalog.selection.{name}") for name in (
        "available", "unavailable", "select_variant", "loading", "error", "demo_action", "quick_buy",
        "preview_action", "cart_action",
    )}
