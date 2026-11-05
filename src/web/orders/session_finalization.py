"""Finalize only the purchased DB-session intent after its order commits.

This merges fresh persisted data. It is not a general transaction protocol for
other concurrent session writers which loaded their session before this lock.
"""
from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils import timezone

from codex_ecommerce.cart import CartError


def require_inventory_session(request):
    if (settings.SESSION_ENGINE != 'django.contrib.sessions.backends.db'
            or settings.SESSION_SAVE_EVERY_REQUEST or not isinstance(request.session, SessionStore)):
        raise CartError('commerce.error.inventory_unavailable')


def finalize_inventory_session(*, request, cart_name, coupon_name, address_name, nonce, values, coupon, address):
    # Session locks are deliberately acquired only after all inventory/order
    # locks have committed, so they cannot create a reverse SKU/session cycle.
    with transaction.atomic():
        record = Session.objects.select_for_update().filter(session_key=request.session.session_key,
            expire_date__gt=timezone.now()).first()
        if record is None:
            request.session = SessionStore(session_key=request.session.session_key)
            return
        current = record.get_decoded()
        fresh = SessionStore(session_key=record.session_key)
        fresh.clear()
        fresh.update(current)
        if (current.get(address_name + '_nonce') == nonce and current.get(cart_name, {}) == values
                and current.get(coupon_name, '') == coupon and current.get(address_name, {}) == address):
            fresh[cart_name] = {}
            fresh.pop(coupon_name, None)
            fresh.pop(address_name + '_nonce', None)
            fresh.save()
        fresh.modified = False
        request.session = fresh
