import re
from decimal import Decimal

from .cart_error import CartError


def validate_quantity(value):
    if isinstance(value, bool) or not re.fullmatch(r"[0-9]{1,2}", str(value)):
        raise CartError("commerce.error.quantity")
    quantity = int(value)
    if not 1 <= quantity <= 20:
        raise CartError("commerce.error.quantity")
    return quantity


def quote_total(items):
    if len(items) > 50:
        raise CartError("commerce.error.lines")
    total = Decimal("0.00")
    seen = set()
    for item in items:
        quantity = validate_quantity(item.quantity)
        if item.sku in seen or not item.sku or item.currency != "EUR":
            raise CartError("commerce.error.variant")
        seen.add(item.sku)
        amount = item.unit_amount
        if not isinstance(amount, Decimal) or not amount.is_finite() or amount < 0:
            raise CartError("commerce.error.variant")
        if amount != amount.quantize(Decimal("0.01")):
            raise CartError("commerce.error.variant")
        if quantity > item.available_quantity:
            raise CartError("commerce.error.unavailable")
        total += amount * quantity
        if total > Decimal("9999999999.99"):
            raise CartError("commerce.error.total")
    return total.quantize(Decimal("0.01"))
