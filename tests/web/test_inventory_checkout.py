from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, connection, transaction
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from codex_ecommerce.cart import CartError
from codex_ecommerce.inventory import OperationContext
from web.cart.models import PromoCode
from web.cart.session_cart import quote
from web.catalog.models import Brand, Category, Product, ProductVariant
from web.inventory import services
from web.inventory.expiry_service import expire_due_reservations
from web.inventory.models import InventoryMovement, ReservationLine, StockBalance
from web.inventory.write_access import service_write
from web.orders.models import Order, OrderLine
from web.orders.persistence import create_test_order
from web.orders.session_finalization import finalize_inventory_session
from web.staff.models import StaffAuditEvent

pytestmark = pytest.mark.django_db(transaction=True)
ADDRESS = dict(email='checkout@example.test', first_name='QA', last_name='Buyer', street='Testweg 1',
    postal_code='10115', city='Berlin', country='DE')


@pytest.fixture(autouse=True)
def inventory_mode(settings):
    settings.SHOP_CHECKOUT_STOCK_MODE = 'inventory_test'
    settings.SHOP_CHECKOUT_RESERVATION_TTL_SECONDS = 1800


@pytest.fixture
def records():
    actor = get_user_model().objects.create_user(username='checkout-stock', is_staff=True, is_superuser=True)
    brand = Brand.objects.create(slug='checkout-brand', name='Brand')
    category = Category.objects.create(slug='checkout-category', name_key='category')
    product = Product.objects.create(slug='checkout-product', model_name='Product', brand=brand, category=category)
    variants = [ProductVariant.objects.create(product=product, sku=f'CHECKOUT-{index}', color_code='black',
        color_name_key='black', size=str(index), price=Decimal('10.00') + index, demo_quantity=0)
        for index in range(2)]
    for variant in variants:
        services.initialize(actor=actor, variant_id=variant.pk, quantity=3,
            context=OperationContext(f'init-{variant.pk}', 'staff', str(actor.pk), 'Isolated checkout QA', 0))
    return actor, variants


def prepare(client, variants, quantity=1):
    for variant in variants:
        assert client.post(reverse('cart:add'), {'sku': variant.sku, 'quantity': quantity}).status_code == 302
    assert client.post(reverse('orders:address'), ADDRESS).status_code == 302
    review = client.get(reverse('payments:review'))
    assert review.status_code == 200
    return review.context['checkout_token']


def post(client, token):
    return client.post(reverse('payments:review'), {'method': 'test', 'checkout_token': token, 'total': '0.01'})


def test_native_guest_inventory_checkout_is_atomic_and_does_not_use_demo(client, records):
    actor, variants = records
    token = prepare(client, variants, quantity=2)
    assert ReservationLine.objects.count() == 0
    assert client.get(reverse('cart:detail')).context['cart']['stock_mode'] == 'inventory_test'
    before = timezone.now()
    result = post(client, token)
    assert result.status_code == 302
    order = Order.objects.get()
    assert order.stock_mode == 'inventory_test' and order.user_id is None and order.is_test
    assert order.status == 'test_created' and order.total_amount == Decimal('42.00')
    assert before + timedelta(seconds=1800) <= order.inventory_hold_expires_at <= timezone.now() + timedelta(seconds=1800)
    assert order.lines.count() == ReservationLine.objects.count() == 2
    for line in ReservationLine.objects.select_related('order_line'):
        assert line.order_line.order_id == order.pk and line.original == line.remaining_reserved == 2
        assert line.state == 'held' and line.expires_at == order.inventory_hold_expires_at
    assert all((balance.on_hand, balance.reserved) == (3, 2) for balance in StockBalance.objects.all())
    movements = InventoryMovement.objects.filter(source='checkout_test')
    assert movements.count() == 2 and all(row.actor_id is None and row.owner == str(order.reference) for row in movements)
    assert all('checkout@example' not in row.reason and token not in row.reason for row in movements)
    assert StaffAuditEvent.objects.filter(action='inventory.reserve', actor__isnull=True).count() == 2
    assert client.get(reverse('cart:detail')).context['cart']['lines'] == []
    assert Client().get(result.url).status_code == 404
    assert post(client, token).url == result.url
    assert Order.objects.count() == 1 and movements.count() == 2


def test_inventory_quote_configured_zero_and_missing_ignore_positive_demo(client, records):
    actor, variants = records
    variant = variants[0]
    variant.demo_quantity = 100
    variant.save()
    services.adjust(actor=actor, variant_id=variant.pk, quantity=0,
        context=OperationContext('zero', 'staff', str(actor.pk), 'QA count', 1))
    assert client.post(reverse('cart:add'), {'sku': variant.sku, 'quantity': 1}).status_code == 400
    unconfigured = ProductVariant.objects.create(product=variant.product, sku='UNCONFIGURED', color_code='black',
        color_name_key='black', size='missing', price='10.00', demo_quantity=100)
    response = client.post(reverse('cart:add'), {'sku': unconfigured.sku, 'quantity': 1})
    assert response.status_code == 400
    assert b'commerce.error.inventory_unconfigured' not in response.content
    assert not Order.objects.exists() and not ReservationLine.objects.exists()


def test_demo_mode_is_explicit_and_persisted_with_no_reservations(client, records, settings):
    _, variants = records
    settings.SHOP_CHECKOUT_STOCK_MODE = 'demo'
    ProductVariant.objects.filter(pk__in=[variant.pk for variant in variants]).update(demo_quantity=3)
    token = prepare(client, variants)
    assert post(client, token).status_code == 302
    order = Order.objects.get()
    assert order.stock_mode == 'demo' and order.inventory_hold_expires_at is None
    assert not ReservationLine.objects.exists()


def test_last_line_shortage_rolls_back_order_and_preserves_all_session_state(client, records):
    actor, variants = records
    PromoCode.objects.create(code='QA', kind='percent', value=10, is_active=True)
    token = prepare(client, variants, quantity=2)
    assert client.post(reverse('cart:coupon_apply'), {'code': 'QA'}).status_code == 302
    token = client.get(reverse('payments:review')).context['checkout_token']
    before = dict(client.session)
    services.adjust(actor=actor, variant_id=variants[-1].pk, quantity=1,
        context=OperationContext('shortage', 'staff', str(actor.pk), 'QA shortage', 1))
    result = post(client, token)
    assert result.status_code == 409
    assert not Order.objects.exists() and not OrderLine.objects.exists() and not ReservationLine.objects.exists()
    assert not InventoryMovement.objects.filter(source='checkout_test').exists()
    assert StockBalance.objects.get(variant=variants[0]).reserved == 0
    for key, value in before.items():
        if key.startswith(('local_cart_', 'local_checkout_')):
            assert client.session[key] == value


@pytest.mark.parametrize('model', ['OrderLine', 'InventoryMovement', 'StaffAuditEvent'])
def test_late_injected_failure_rolls_back_every_new_record_and_preserves_cart(client, records, model):
    _, variants = records
    token = prepare(client, variants)
    target = OrderLine if model == 'OrderLine' else InventoryMovement if model == 'InventoryMovement' else StaffAuditEvent
    original_create = target.objects.create
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        if len(calls) == 2:
            raise RuntimeError('injected checkout failure')
        return original_create(**kwargs)

    with patch.object(target.objects, 'create', side_effect=create):
        with pytest.raises(RuntimeError, match='injected checkout failure'):
            post(client, token)
    assert not Order.objects.exists() and not OrderLine.objects.exists() and not ReservationLine.objects.exists()
    assert not InventoryMovement.objects.filter(source='checkout_test').exists()
    assert not StaffAuditEvent.objects.filter(actor__isnull=True).exists()
    assert all(balance.reserved == 0 for balance in StockBalance.objects.all())
    assert client.get(reverse('cart:detail')).context['cart']['item_count'] == 2
    assert post(client, token).status_code == 302


def test_old_replay_after_expiry_preserves_new_cart_and_intent(client, records, settings):
    actor, variants = records
    token = prepare(client, variants[:1])
    first = post(client, token)
    order = Order.objects.get()
    deadline = order.inventory_hold_expires_at
    assert expire_due_reservations(actor=actor, now=deadline).expired == 1
    new_token = prepare(client, variants[1:])
    session_before = dict(client.session)
    settings.SHOP_CHECKOUT_STOCK_MODE = 'demo'
    assert post(client, token).url == first.url
    assert dict(client.session) == session_before and new_token != token
    assert Order.objects.count() == ReservationLine.objects.count() == 1
    assert ReservationLine.objects.get().state == 'closed'
    assert Order.objects.get().stock_mode == 'inventory_test'


def test_authenticated_checkout_does_not_give_staff_rights_or_inventory_pii(client, records):
    _, variants = records
    user = get_user_model().objects.create_user(username='checkout-buyer')
    client.force_login(user)
    token = prepare(client, variants[:1])
    result = post(client, token)
    assert result.status_code == 302 and Order.objects.get().user_id == user.pk
    assert not user.is_staff and not user.user_permissions.exists()
    assert InventoryMovement.objects.get(source='checkout_test').actor_id is None
    other = Client()
    other.force_login(get_user_model().objects.create_user(username='other-buyer'))
    assert other.get(result.url).status_code == 404
    assert post(other, token).status_code == 409


def test_inventory_checkout_rejects_outer_atomic_before_effects(client, records):
    _, variants = records
    token = prepare(client, variants[:1])
    request = RequestFactory().post(reverse('payments:review'))
    request.user = AnonymousUser()
    request.session = client.session
    with transaction.atomic(), pytest.raises(CartError, match='commerce.error.inventory_retry'):
        create_test_order(request, token)
    assert not Order.objects.exists() and not ReservationLine.objects.exists()


def test_native_csrf_token_signature_and_nonce_stay_required(records):
    _, variants = records
    strict = Client(enforce_csrf_checks=True)
    assert strict.post(reverse('cart:add'), {'sku': variants[0].sku, 'quantity': 1}).status_code == 403
    ordinary = Client()
    token = prepare(ordinary, variants[:1])
    assert post(ordinary, token + 'tampered').status_code == 409
    assert strict.post(reverse('payments:review'), {'method': 'test', 'checkout_token': token}).status_code == 403
    payload = signing.loads(token, salt='local-test-checkout')
    session = ordinary.session
    session['local_checkout_address_guest_nonce'] = 'new-server-intent'
    session.save()
    assert post(ordinary, token).status_code == 409
    assert not Order.objects.exists() and payload['nonce'] != 'new-server-intent'


@pytest.mark.parametrize('mutation', ['price', 'coupon', 'address'])
def test_stale_price_coupon_address_do_not_create_any_hold(client, records, mutation):
    _, variants = records
    token = prepare(client, variants[:1])
    if mutation == 'price':
        ProductVariant.objects.filter(pk=variants[0].pk).update(price='90.00')
    elif mutation == 'coupon':
        PromoCode.objects.create(code='NEW', kind='fixed', value=1, is_active=True)
        client.post(reverse('cart:coupon_apply'), {'code': 'NEW'})
    else:
        client.post(reverse('orders:address'), ADDRESS | {'city': 'Hamburg'})
    assert post(client, token).status_code == 409
    assert not Order.objects.exists() and not ReservationLine.objects.exists()


def test_inventory_quote_query_count_is_bounded_without_per_sku_queries(client, records):
    _, variants = records
    prepare(client, variants)
    request = RequestFactory().get(reverse('cart:detail'))
    request.user = AnonymousUser()
    request.session = client.session
    request.session.get('local_cart_guest')
    counts = []
    for values in ({variants[0].sku: 1}, {variant.sku: 1 for variant in variants}):
        with CaptureQueriesContext(connection) as queries:
            result = quote(request, values=values)
        assert result['can_checkout']
        counts.append(len(queries))
    assert counts[0] == counts[1] and counts[0] <= 4


def test_finalizer_preserves_new_persisted_cart_intent_and_other_session_keys(client, records):
    _, variants = records
    token = prepare(client, variants[:1])

    def concurrent_change(**kwargs):
        fresh = SessionStore(session_key=kwargs['request'].session.session_key)
        fresh['local_cart_guest'] = {variants[1].sku: 2}
        fresh['local_cart_guest_coupon'] = 'NEXT'
        fresh['local_checkout_address_guest'] = ADDRESS | {'city': 'Hamburg'}
        fresh['local_checkout_address_guest_nonce'] = 'next-intent'
        fresh['unrelated_feature_key'] = 'keep'
        fresh.save()
        finalize_inventory_session(**kwargs)

    with patch('web.orders.persistence.finalize_inventory_session', side_effect=concurrent_change):
        assert post(client, token).status_code == 302
    current = client.session
    assert current['local_cart_guest'] == {variants[1].sku: 2}
    assert current['local_cart_guest_coupon'] == 'NEXT'
    assert current['local_checkout_address_guest']['city'] == 'Hamburg'
    assert current['local_checkout_address_guest_nonce'] == 'next-intent'
    assert current['unrelated_feature_key'] == 'keep'
    assert Order.objects.count() == ReservationLine.objects.count() == 1


def test_session_failure_after_order_commit_has_safe_replay_without_duplicate_holds(client, records):
    _, variants = records
    token = prepare(client, variants[:1])
    before = dict(client.session)
    with patch('web.orders.persistence.finalize_inventory_session', side_effect=RuntimeError('session failure')):
        with pytest.raises(RuntimeError, match='session failure'):
            post(client, token)
    assert Order.objects.count() == ReservationLine.objects.count() == 1
    assert dict(client.session) == before
    assert post(client, token).status_code == 302
    assert Order.objects.count() == ReservationLine.objects.count() == 1
    assert dict(client.session) == before


@pytest.mark.parametrize('engine,save_every', [('django.contrib.sessions.backends.signed_cookies', False),
    ('django.contrib.sessions.backends.db', True)])
def test_inventory_checkout_rejects_unsupported_session_configuration_before_effects(client, records, settings, engine, save_every):
    _, variants = records
    token = prepare(client, variants[:1])
    request = RequestFactory().post(reverse('payments:review'))
    request.user, request.session = AnonymousUser(), client.session
    settings.SESSION_ENGINE = engine
    settings.SESSION_SAVE_EVERY_REQUEST = save_every
    with pytest.raises(CartError, match='commerce.error.inventory_unavailable'):
        create_test_order(request, token)
    assert not Order.objects.exists() and not ReservationLine.objects.exists()


def test_failed_checkout_keeps_independently_committed_expiry_without_staff_impersonation(client, records):
    actor, variants = records
    now = timezone.now()
    services.reserve(actor=actor, variant_id=variants[0].pk, reservation_id='old-hold', quantity=1,
        context=OperationContext('old-hold', 'staff', str(actor.pk), 'QA hold', 1), now=now,
        expires_at=now + timedelta(seconds=1))
    token = prepare(client, variants)
    ProductVariant.objects.filter(pk=variants[1].pk).update(price='99.00')
    with patch('web.orders.persistence.timezone.now', return_value=now + timedelta(seconds=2)):
        assert post(client, token).status_code == 409
    assert not Order.objects.exists() and not OrderLine.objects.exists()
    assert ReservationLine.objects.get(reference='old-hold').state == 'closed'
    expiry = InventoryMovement.objects.get(kind='expire')
    assert expiry.actor_id is None and expiry.source == 'inventory_expiry' and expiry.owner == 'system'
    assert not InventoryMovement.objects.filter(source='checkout_test').exists()
    assert client.get(reverse('cart:detail')).context['cart']['item_count'] == 2


def test_signed_same_intent_changed_payload_conflicts_with_original_order(client, records):
    _, variants = records
    token = prepare(client, variants[:1])
    assert post(client, token).status_code == 302
    payload = signing.loads(token, salt='local-test-checkout')
    changed = signing.dumps(payload | {'fingerprint': 'f' * 64}, salt='local-test-checkout')
    assert post(client, changed).status_code == 409
    assert Order.objects.count() == ReservationLine.objects.count() == 1


def test_order_line_binding_is_unique_and_immutable_in_normal_write_scope(client, records):
    _, variants = records
    assert post(client, prepare(client, variants)).status_code == 302
    reservations = list(ReservationLine.objects.order_by('reference'))
    with pytest.raises(IntegrityError):
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute('UPDATE inventory_reservationline SET order_line_id = %s WHERE reference = %s',
                [reservations[0].order_line_id, reservations[1].reference])
    reservations[0].order_line_id = None
    with service_write(), pytest.raises(PermissionDenied):
        reservations[0].save()


def test_preflight_global_time_budget_refuses_checkout_without_unbounded_drain(client, records):
    actor, variants = records
    now = timezone.now()
    services.reserve(actor=actor, variant_id=variants[0].pk, reservation_id='backlog', quantity=1,
        context=OperationContext('backlog', 'staff', str(actor.pk), 'QA backlog', 1),
        now=now, expires_at=now + timedelta(seconds=1))
    token = prepare(client, variants[:1])
    before = dict(client.session)
    with patch('web.orders.persistence.timezone.now', return_value=now + timedelta(seconds=2)):
        with patch('web.inventory.checkout_adapter.monotonic', side_effect=[0.0, 6.0]):
            response = post(client, token)
    assert response.status_code == 409 and response.context['checkout_error'] == 'commerce.error.inventory_retry'
    assert not Order.objects.exists() and InventoryMovement.objects.filter(kind='expire').count() == 0
    assert dict(client.session) == before


def test_repeated_add_of_one_sku_creates_one_aggregated_reservation(client, records):
    _, variants = records
    token = prepare(client, variants[:1])
    assert client.post(reverse('cart:add'), {'sku': variants[0].sku, 'quantity': 1}).status_code == 302
    token = client.get(reverse('payments:review')).context['checkout_token']
    assert post(client, token).status_code == 302
    assert OrderLine.objects.get().quantity == ReservationLine.objects.get().original == 2


def test_prepared_schema_does_not_create_inventory_for_historical_demo_orders(records):
    _, variants = records
    legacy = Order.objects.create(total_amount='10.00', is_test=True)
    OrderLine.objects.create(order=legacy, sku=variants[0].sku, product_name='Legacy TEST', quantity=1, unit_amount='10.00')
    assert legacy.stock_mode == 'demo' and legacy.inventory_hold_expires_at is None
    assert legacy.checkout_fingerprint == '' and not ReservationLine.objects.exists()
