"""Atomic TEST order persistence with an explicit demo or inventory stock mode."""
from datetime import timedelta

from django.core import signing
from django.db import IntegrityError, OperationalError, connection, transaction
from django.utils import timezone

from codex_ecommerce.cart import CartError
from codex_ecommerce.inventory import InsufficientStockError, InventoryError, StockNotConfiguredError
from web.cart.promotions import coupon_key, selected_code
from web.cart.session_cart import cart_key, quantities, quote
from web.catalog.models import ProductVariant
from web.inventory.checkout_adapter import preflight_checkout, recheck_due_checkout, reserve_order_line
from web.inventory.checkout_policy import reservation_ttl, stock_mode
from web.inventory.expiry_backlog_error import ExpiryBacklogError
from web.inventory.expiry_transaction_error import ExpiryTransactionError
from web.inventory.operation_store import unique_constraint
from web.inventory.write_access import service_write
from web.orders.address_form import CheckoutAddressForm
from web.orders.address_snapshot import billing_address, shipping_address
from web.orders.checkout_state import address_key, checkout_fingerprint, read_token, session_owner, token_key
from web.orders.models import Order, OrderLine
from web.orders.session_finalization import finalize_inventory_session, require_inventory_session


def _existing(request, identity, owner, payload):
    orders = Order.objects.filter(checkout_token=identity, session_owner=owner, is_test=True)
    orders = orders.filter(user=request.user) if request.user.is_authenticated else orders.filter(user__isnull=True)
    order = orders.first()
    if order is not None and order.checkout_fingerprint and order.checkout_fingerprint != payload['fingerprint']:
        raise CartError('commerce.error.stale')
    return order


def _stock_error(error):
    if isinstance(error, StockNotConfiguredError):
        return 'commerce.error.inventory_unconfigured'
    if isinstance(error, InsufficientStockError):
        return 'commerce.error.inventory_shortage'
    if isinstance(error, (ExpiryBacklogError, ExpiryTransactionError)):
        return 'commerce.error.inventory_retry'
    return 'commerce.error.inventory_unavailable'


def create_test_order(request, token):
    try:
        payload = read_token(request, token)
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        raise CartError('commerce.error.review') from None
    identity, owner = token_key(payload), session_owner(request)
    existing = _existing(request, identity, owner, payload)
    if existing is not None:
        return existing
    address_name = address_key(request)
    if request.session.get(address_name + '_nonce') != payload['nonce']:
        existing = _existing(request, identity, owner, payload)
        if existing is not None:
            return existing
        raise CartError('commerce.error.review')
    mode = stock_mode()
    if mode == 'inventory_test':
        if connection.in_atomic_block or not connection.get_autocommit():
            raise CartError('commerce.error.inventory_retry')
        require_inventory_session(request)
        ttl = reservation_ttl()
    address = dict(request.session.get(address_name, {}))
    form = CheckoutAddressForm(address)
    if not form.is_valid():
        raise CartError('commerce.error.address')
    values, coupon_code = quantities(request), selected_code(request)
    if not values or len(values) > 50:
        raise CartError('commerce.error.lines')
    for sku, quantity in values.items():
        if not isinstance(sku, str) or not sku or len(sku) > 100 or type(quantity) is not int or not 1 <= quantity <= 20:
            raise CartError('commerce.error.quantity')
    if mode == 'inventory_test':
        variant_ids = list(ProductVariant.objects.filter(sku__in=values).order_by('pk').values_list('pk', flat=True))
        try:
            preflight_checkout(variant_ids=variant_ids, now=timezone.now())
        except InventoryError as error:
            raise CartError(_stock_error(error)) from None
    for attempt in range(2):
        try:
            with transaction.atomic(), service_write():
                cart = quote(request, values=values, lock=True)
                # Recheck after variant locks: another submit may have held
                # these same units while this transaction waited.
                existing = _existing(request, identity, owner, payload)
                if existing is not None:
                    return existing
                now = timezone.now()
                if mode == 'inventory_test':
                    recheck_due_checkout(variant_ids=[line['variant_id'] for line in cart['lines']
                        if line['variant_id'] is not None], now=now)
                if not cart['can_checkout']:
                    raise CartError(cart['errors'][0] if cart['errors'] else 'commerce.error.unavailable')
                if payload['fingerprint'] != checkout_fingerprint(cart, form.cleaned_data):
                    raise CartError('commerce.error.stale')
                expires_at = now + timedelta(seconds=ttl) if mode == 'inventory_test' else None
                order = Order.objects.create(status='test_created', currency='EUR', total_amount=cart['total'],
                    user=request.user if request.user.is_authenticated else None, session_owner=owner,
                    checkout_token=identity, checkout_fingerprint=payload['fingerprint'], stock_mode=mode,
                    inventory_hold_expires_at=expires_at, address=shipping_address(form.cleaned_data),
                    billing_address=billing_address(form.cleaned_data), is_test=True,
                    shipping_amount=cart['shipping_amount'], subtotal_amount=cart['subtotal'],
                    discount_amount=cart['discount_amount'], coupon_code=cart['coupon_code'])
                for line in cart['lines']:
                    order_line = OrderLine.objects.create(order=order, sku=line['sku'], product_name=line['name'],
                        brand_name=line['brand'], colour_name=line['colour_name'], size_name=line['size'],
                        quantity=line['quantity'], unit_amount=line['unit_amount'], photo_url=line['photo_url'])
                    if mode == 'inventory_test':
                        reserve_order_line(order=order, order_line=order_line,
                            balance=cart['_inventory_balances'][line['variant_id']], expires_at=expires_at, now=now)
                if mode == 'inventory_test':
                    transaction.on_commit(lambda: finalize_inventory_session(request=request, cart_name=cart_key(request),
                        coupon_name=coupon_key(request), address_name=address_name, nonce=payload['nonce'],
                        values=values, coupon=coupon_code, address=address))
            break
        except IntegrityError as error:
            if unique_constraint(error) != 'orders_order_checkout_token_key':
                raise
            existing = _existing(request, identity, owner, payload)
            if existing is None:
                raise
            return existing
        except InventoryError as error:
            raise CartError(_stock_error(error)) from None
        except OperationalError as error:
            if getattr(error.__cause__, 'sqlstate', None) in {'40001', '40P01'} and attempt == 0:
                continue
            raise CartError('commerce.error.inventory_unavailable') from None
    if mode == 'demo':
        # Keep the explicitly selected historical prototype session behavior;
        # inventory_test finalizes against fresh persisted state after commit.
        if (request.session.get(address_name + '_nonce') == payload['nonce']
                and quantities(request) == values and selected_code(request) == coupon_code):
            request.session[cart_key(request)] = {}
            request.session.pop(coupon_key(request), None)
            request.session.pop(address_name + '_nonce', None)
    return order
