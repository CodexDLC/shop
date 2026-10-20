"""Django session adapter. Catalog prices and availability remain server-owned."""
from decimal import Decimal

from django.urls import reverse

from codex_ecommerce.cart import CartError, CartItem, quote_total, validate_quantity
from web.catalog.models import ProductVariant
from web.localization import translate_text


def cart_key(request):
    # A login or account switch does not reveal another principal's cart.
    return f"local_cart_user_{request.user.pk}" if request.user.is_authenticated else "local_cart_guest"


def quantities(request):
    return dict(request.session.get(cart_key(request), {}))


def quote(request, *, values=None, lock=False):
    values = quantities(request) if values is None else values
    variants = ProductVariant.objects.select_related("product__brand").prefetch_related("product__images")
    if lock:
        variants = variants.select_for_update()
    rows = {variant.sku: variant for variant in variants.filter(sku__in=values)}
    items, lines, errors = [], [], []
    for sku, quantity in values.items():
        variant = rows.get(sku)
        valid = variant and variant.is_active and variant.product.is_active and variant.currency == "EUR"
        if not valid:
            errors.append("commerce.error.variant")
        amount = variant.price if variant else Decimal("0.00")
        available = min(20, variant.demo_quantity) if valid else 0
        item = CartItem(sku, quantity, amount, "EUR", available)
        try:
            quote_total((item,))
        except CartError as exc:
            errors.append(str(exc))
        items.append(item)
        images = list(variant.product.images.all()) if variant else []
        image = next((row for row in images if row.color_code == variant.color_code), None) if variant else None
        image = image or next((row for row in images if not row.color_code), None)
        lines.append({
            "sku": sku, "quantity": quantity, "unit_amount": amount, "line_amount": amount * quantity,
            "name": variant.product.model_name if variant else sku,
            "brand": variant.product.brand.name if variant else "",
            "colour_name": translate_text(variant.color_name_key) if variant else "",
            "size": variant.size if variant else "", "max_quantity": available,
            "photo_url": image.image_url if image else "",
            "detail_url": reverse("catalog:detail", kwargs={"slug": variant.product.slug}) if valid else "",
            "available": bool(valid and quantity <= available),
        })
    if len(lines) > 50:
        errors.append("commerce.error.lines")
    total = sum((line["line_amount"] for line in lines), Decimal("0.00"))
    if not errors:
        try:
            total = quote_total(tuple(items))
        except CartError as exc:
            errors.append(str(exc))
    return {"currency": "EUR", "lines": lines, "subtotal": total, "total": total,
            "shipping_amount": Decimal("0.00"), "item_count": sum(values.values()),
            "errors": list(dict.fromkeys(errors)), "can_checkout": bool(lines) and not errors}


def change_cart(request, sku, value=None, *, remove=False, add=False):
    values = quantities(request)
    if not isinstance(sku, str) or not sku or len(sku) > 100:
        raise CartError("commerce.error.variant")
    if remove:
        values.pop(sku, None)
    else:
        quantity = validate_quantity(value)
        if add:
            quantity = validate_quantity(quantity + values.get(sku, 0))
        if not add and sku not in values:
            raise CartError("commerce.error.variant")
        values[sku] = quantity
        # Validate the changed SKU only; unavailable older lines can still be removed/repaired.
        if len(values) > 50:
            raise CartError("commerce.error.lines")
        result = quote(request, values={sku: quantity})
        if result["errors"]:
            raise CartError(result["errors"][0])
    request.session[cart_key(request)] = values
