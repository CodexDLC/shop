from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .cart_error import CartError

_CENT = Decimal('0.01')
_MAX = Decimal('9999999999.99')


def _money(value, *, positive=False):
    if not isinstance(value, Decimal) or not value.is_finite():
        raise CartError('commerce.error.coupon_invalid')
    try:
        valid = 0 <= value <= _MAX and value == value.quantize(_CENT)
    except InvalidOperation:
        valid = False
    if not valid or (positive and value <= 0):
        raise CartError('commerce.error.coupon_invalid')
    return value


def discount_amount(subtotal, rule):
    """Return an EUR discount; currency, precision and limits are explicit."""
    subtotal = _money(subtotal)
    value = _money(rule.value, positive=True)
    minimum = _money(rule.min_subtotal)
    if rule.currency != 'EUR' or rule.kind not in ('percent', 'fixed'):
        raise CartError('commerce.error.coupon_invalid')
    if rule.kind == 'percent' and value > 100:
        raise CartError('commerce.error.coupon_invalid')
    if subtotal < minimum:
        raise CartError('commerce.error.coupon_minimum')
    amount = subtotal * value / 100 if rule.kind == 'percent' else value
    return min(subtotal, amount).quantize(_CENT, rounding=ROUND_HALF_UP)
