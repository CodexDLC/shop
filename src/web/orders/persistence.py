"""Atomic test-order persistence; no payment, shipping, mail or stock adapter."""
from django.core import signing
from django.db import IntegrityError, transaction

from codex_ecommerce.cart import CartError
from web.cart.promotions import coupon_key, selected_code
from web.cart.session_cart import cart_key, quantities, quote
from web.orders.address_form import CheckoutAddressForm
from web.orders.address_snapshot import billing_address, shipping_address
from web.orders.checkout_state import address_key, checkout_fingerprint, read_token, session_owner, token_key
from web.orders.models import Order, OrderLine


def create_test_order(request, token):
    try:
        payload = read_token(request, token)
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        raise CartError("commerce.error.review") from None
    identity = token_key(payload)
    owner = session_owner(request)
    existing = Order.objects.filter(checkout_token=identity, session_owner=owner, is_test=True).first()
    if existing:
        return existing
    address = request.session.get(address_key(request), {})
    form = CheckoutAddressForm(address)
    if not form.is_valid():
        raise CartError("commerce.error.address")
    values = quantities(request)
    coupon_code = selected_code(request)
    try:
        with transaction.atomic():
            cart = quote(request, values=values, lock=True)
            if not cart["can_checkout"]:
                raise CartError(cart["errors"][0] if cart["errors"] else "commerce.error.unavailable")
            if payload["fingerprint"] != checkout_fingerprint(cart, form.cleaned_data):
                raise CartError("commerce.error.stale")
            order = Order.objects.create(
                status="test_created", currency="EUR", total_amount=cart["total"],
                user=request.user if request.user.is_authenticated else None,
                session_owner=owner, checkout_token=identity, address=shipping_address(form.cleaned_data),
                billing_address=billing_address(form.cleaned_data), is_test=True,
                shipping_amount=cart["shipping_amount"], subtotal_amount=cart["subtotal"],
                discount_amount=cart["discount_amount"], coupon_code=cart["coupon_code"],
            )
            OrderLine.objects.bulk_create([OrderLine(
                order=order, sku=line["sku"], product_name=line["name"], brand_name=line["brand"],
                colour_name=line["colour_name"], size_name=line["size"], quantity=line["quantity"],
                unit_amount=line["unit_amount"], photo_url=line["photo_url"],
            ) for line in cart["lines"]])
    except IntegrityError:
        # A unique operation key is the final authority for simultaneous submissions.
        existing = Order.objects.filter(checkout_token=identity, session_owner=owner, is_test=True).first()
        if existing is None:
            raise
        return existing
    if quantities(request) == values and selected_code(request) == coupon_code:
        request.session[cart_key(request)] = {}
        request.session.pop(coupon_key(request), None)
    request.session.pop(address_key(request) + "_nonce", None)
    return order
