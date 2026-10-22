"""Current promotion rules, owned by the Django/session adapter."""
import hashlib
import json
import re

from django.utils import timezone

from codex_ecommerce.cart import CartError, DiscountRule, discount_amount
from web.cart.models import PromoCode


def coupon_key(request):
    from web.cart.session_cart import cart_key
    return cart_key(request) + '_coupon'


def selected_code(request):
    return request.session.get(coupon_key(request), '')


def normalize_code(value):
    code = value.strip().upper() if isinstance(value, str) else ''
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{0,31}', code, flags=re.ASCII):
        raise CartError('commerce.error.coupon_invalid')
    return code


def promotion_quote(code, subtotal, *, lock=False):
    code = normalize_code(code)
    rules = PromoCode.objects
    if lock:
        rules = rules.select_for_update()
    rule = rules.filter(code=code).first()
    if rule is None or not rule.is_active:
        raise CartError('commerce.error.coupon_invalid')
    now = timezone.now()
    if rule.starts_at and now < rule.starts_at:
        raise CartError('commerce.error.coupon_invalid')
    if rule.ends_at and now >= rule.ends_at:
        raise CartError('commerce.error.coupon_expired')
    amount = discount_amount(subtotal, DiscountRule(rule.kind, rule.value, rule.min_subtotal, rule.currency))
    snapshot = {field: getattr(rule, field) for field in (
        'code', 'kind', 'value', 'min_subtotal', 'currency', 'is_active', 'starts_at', 'ends_at',
    )}
    signature = hashlib.sha256(json.dumps(snapshot, default=str, sort_keys=True).encode()).hexdigest()
    return {'code': code, 'kind': rule.kind, 'value': rule.value, 'discount_amount': amount,
            'signature': signature}
