"""Django session adapter. Catalog prices and availability remain server-owned."""
from decimal import Decimal

from django.urls import reverse

from codex_ecommerce.cart import CartError, CartItem, quote_total, validate_quantity
from web.cart.promotions import promotion_quote, selected_code
from web.catalog.category_visibility import visible_category_ids
from web.catalog.models import Product, ProductVariant
from web.inventory.availability import InventoryAvailability
from web.inventory.availability_queries import with_availability
from web.inventory.checkout_policy import stock_mode
from web.inventory.models import StockBalance
from web.localization import translate_text


def cart_key(request):
    # A login or account switch does not reveal another principal's cart.
    return f"local_cart_user_{request.user.pk}" if request.user.is_authenticated else "local_cart_guest"


def quantities(request):
    return dict(request.session.get(cart_key(request), {}))


def quote(request, *, values=None, lock=False, ignore_coupon=False):
    values = quantities(request) if values is None else values
    mode = stock_mode()
    if not isinstance(values, dict) or len(values) > 50:
        raise CartError('commerce.error.lines')
    for sku, quantity in values.items():
        if not isinstance(sku, str) or not sku or len(sku) > 100:
            raise CartError('commerce.error.variant')
        validate_quantity(quantity)
    balances = {}
    if lock:
        # Shared order with staff/expiry: all parents, then all balances. Lock
        # products afterwards; joined select_related must not add implicit locks.
        targets = list(ProductVariant.objects.filter(sku__in=values).order_by('pk')
            .select_for_update(of=('self',)))
        if mode == 'inventory_test':
            balances = {row.variant_id: row for row in StockBalance.objects.select_for_update()
                .filter(variant_id__in=[row.pk for row in targets], location_id='main').order_by('variant_id')}
        list(Product.objects.select_for_update().filter(pk__in={row.product_id for row in targets}).order_by('pk'))
    variants = ProductVariant.objects.select_related("product__brand").prefetch_related("product__images")
    # The locked path projects the balances already acquired above. Other reads
    # attach the same scalar quantity to each bounded variant query.
    if not lock:
        variants = with_availability(variants)
    rows = {variant.sku: variant for variant in variants.filter(sku__in=values,
        product__category_id__in=visible_category_ids()).order_by('pk')}
    items, lines, errors = [], [], []
    for sku, quantity in values.items():
        variant = rows.get(sku)
        valid = variant and variant.is_active and variant.product.is_active and variant.currency == "EUR"
        if not valid:
            errors.append("commerce.error.variant")
        amount = variant.price if variant else Decimal("0.00")
        availability = InventoryAvailability.from_variant(variant, balances=balances if lock else None) if valid else None
        if availability is not None and not availability.configured:
            errors.append('commerce.error.inventory_unconfigured')
        available = min(20, availability.quantity) if availability is not None and availability.configured else 0
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
            "variant_id": variant.pk if variant else None,
            "sku": sku, "quantity": quantity, "unit_amount": amount, "line_amount": amount * quantity,
            "name": variant.product.model_name if variant else sku,
            "brand": variant.product.brand.name if variant else "",
            "colour_name": translate_text(variant.color_name_key) if variant else "",
            "size": variant.size if variant else "", "max_quantity": available,
            "photo_url": image.public_url if image else "",
            "detail_url": reverse("catalog:detail", kwargs={"slug": variant.product.slug}) if valid else "",
            "available": bool(valid and quantity <= available),
            "stock_configured": availability.configured if availability is not None else False,
        })
    if len(lines) > 50:
        errors.append("commerce.error.lines")
    total = sum((line["line_amount"] for line in lines), Decimal("0.00"))
    if not errors:
        try:
            total = quote_total(tuple(items))
        except CartError as exc:
            errors.append(str(exc))
    subtotal = total
    code = '' if ignore_coupon else selected_code(request)
    coupon = None
    discount = Decimal('0.00')
    if code:
        try:
            coupon = promotion_quote(code, subtotal, lock=lock)
            discount = coupon['discount_amount']
        except CartError as exc:
            errors.append(str(exc))
    return {"currency": "EUR", "stock_mode": mode, "lines": lines, "subtotal": subtotal, "total": subtotal - discount,
            "_inventory_balances": balances,
            "discount_amount": discount, "coupon_code": code, "coupon": coupon,
            "coupon_signature": coupon['signature'] if coupon else '',
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
        result = quote(request, values={sku: quantity}, ignore_coupon=True)
        if result["errors"]:
            raise CartError(result["errors"][0])
    request.session[cart_key(request)] = values
