from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.db import close_old_connections, connection
from django.db.models import Sum
from django.test import Client, RequestFactory
from django.urls import reverse
from django.utils import timezone

from codex_ecommerce.cart import CartError
from codex_ecommerce.inventory import OperationContext, StaleRevisionError
from web.catalog.models import Brand, Category, Product, ProductVariant
from web.inventory import services
from web.inventory.expiry_service import expire_due_reservations
from web.inventory.models import InventoryMovement, ReservationLine, StockBalance
from web.orders.models import Order, OrderLine
from web.orders.persistence import create_test_order
from web.staff.models import StaffAuditEvent

pytestmark = [pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != 'postgresql', reason='Requires isolated PostgreSQL test database')]
ADDRESS = dict(email='qa-checkout@example.test', first_name='QA', last_name='Buyer', street='Testweg 1',
    postal_code='10115', city='Berlin', country='DE')


@pytest.fixture(autouse=True)
def inventory_mode(settings):
    settings.SHOP_CHECKOUT_STOCK_MODE = 'inventory_test'
    settings.SHOP_CHECKOUT_RESERVATION_TTL_SECONDS = 1800


@pytest.fixture
def records():
    actor = get_user_model().objects.create_user(username='checkout-race-stock', is_staff=True, is_superuser=True)
    brand = Brand.objects.create(slug='checkout-race', name='Brand')
    category = Category.objects.create(slug='checkout-race', name_key='category')
    product = Product.objects.create(slug='checkout-race', model_name='Product', brand=brand, category=category)
    variants = [ProductVariant.objects.create(product=product, sku=f'CHECKOUT-RACE-{index}', color_code='black',
        color_name_key='black', size=str(index), price='10.00', demo_quantity=0) for index in range(2)]
    for variant in variants:
        services.initialize(actor=actor, variant_id=variant.pk, quantity=1,
            context=OperationContext(f'init-{variant.pk}', 'staff', str(actor.pk), 'Isolated checkout race QA', 0))
    return actor, variants


def prepare(client, variants):
    for variant in variants:
        assert client.post(reverse('cart:add'), {'sku': variant.sku, 'quantity': 1}).status_code == 302
    assert client.post(reverse('orders:address'), ADDRESS).status_code == 302
    response = client.get(reverse('payments:review'))
    assert response.status_code == 200
    return response.context['checkout_token']


def request_snapshot(client):
    request = RequestFactory().post(reverse('payments:review'))
    request.user = AnonymousUser()
    request.session = SessionStore(session_key=client.session.session_key)
    list(request.session.items())
    return request


def race(functions):
    start = Barrier(len(functions))

    def run(function):
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '5s'")
                cursor.execute("SET statement_timeout = '10s'")
                cursor.execute('SELECT pg_backend_pid()')
                backend = cursor.fetchone()[0]
            start.wait(timeout=10)
            try:
                return backend, function()
            except (CartError, StaleRevisionError) as error:
                return backend, error
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=len(functions)) as executor:
        futures = [executor.submit(run, function) for function in functions]
        results = [future.result(timeout=20) for future in futures]
    assert len({backend for backend, _ in results}) == len(functions)
    return [value for _, value in results]


def assert_conserved(variants):
    for variant in variants:
        stock = StockBalance.objects.get(variant=variant)
        totals = ReservationLine.objects.filter(variant=variant).aggregate(remaining=Sum('remaining_reserved'))
        assert stock.reserved == (totals['remaining'] or 0)
        assert 0 <= stock.reserved <= stock.on_hand


def test_two_customers_cannot_checkout_the_same_last_unit(records):
    _, variants = records
    clients = [Client(), Client()]
    tokens = [prepare(client, variants[:1]) for client in clients]
    requests = [request_snapshot(client) for client in clients]
    results = race([lambda: create_test_order(requests[0], tokens[0]),
        lambda: create_test_order(requests[1], tokens[1])])
    assert sum(isinstance(result, CartError) for result in results) == 1
    assert Order.objects.count() == OrderLine.objects.count() == ReservationLine.objects.count() == 1
    loser = next(index for index, result in enumerate(results) if isinstance(result, CartError))
    assert clients[loser].session['local_cart_guest'] == {variants[0].sku: 1}
    assert_conserved(variants)


def test_same_intent_double_submit_returns_one_order_one_original_hold(records):
    _, variants = records
    client = Client()
    token = prepare(client, variants[:1])
    requests = [request_snapshot(client), request_snapshot(client)]
    orders = race([lambda: create_test_order(requests[0], token), lambda: create_test_order(requests[1], token)])
    assert all(isinstance(order, Order) for order in orders) and orders[0].pk == orders[1].pk
    assert Order.objects.count() == OrderLine.objects.count() == ReservationLine.objects.count() == 1
    line = ReservationLine.objects.get()
    assert line.revision == 1 and line.expires_at == orders[0].inventory_hold_expires_at
    assert InventoryMovement.objects.filter(source='checkout_test').count() == 1
    assert_conserved(variants)


def test_opposite_cart_order_locks_all_sku_consistently(records):
    _, variants = records
    clients = [Client(), Client()]
    tokens = [prepare(clients[0], variants), prepare(clients[1], list(reversed(variants)))]
    requests = [request_snapshot(client) for client in clients]
    results = race([lambda: create_test_order(requests[0], tokens[0]),
        lambda: create_test_order(requests[1], tokens[1])])
    assert sum(isinstance(result, CartError) for result in results) == 1
    assert Order.objects.count() == 1 and OrderLine.objects.count() == ReservationLine.objects.count() == 2
    assert InventoryMovement.objects.filter(source='checkout_test').count() == 2
    assert_conserved(variants)


def test_same_intent_disjoint_signed_payloads_use_real_unique_constraint_recovery(records):
    _, variants = records
    product = variants[1].product
    variants[1].product = Product.objects.create(slug='checkout-disjoint-product', model_name='Other product',
        brand=product.brand, category=product.category)
    variants[1].save(update_fields=['product'])
    client = Client()
    first_token = prepare(client, variants[:1])
    first_request = request_snapshot(client)
    # Cart edits preserve the server address intent nonce; GET produces another
    # genuine signed payload with the same owner/nonce and another fingerprint.
    client.post(reverse('cart:remove'), {'sku': variants[0].sku})
    client.post(reverse('cart:add'), {'sku': variants[1].sku, 'quantity': 1})
    second_token = client.get(reverse('payments:review')).context['checkout_token']
    second_request = request_snapshot(client)
    create_order = Order.objects.create
    both_ready = Barrier(2)

    def synchronized_create(**kwargs):
        both_ready.wait(timeout=10)
        return create_order(**kwargs)

    with patch('web.orders.persistence.Order.objects.create', side_effect=synchronized_create):
        results = race([lambda: create_test_order(first_request, first_token),
            lambda: create_test_order(second_request, second_token)])
    errors = [result for result in results if isinstance(result, CartError)]
    assert len(errors) == 1 and str(errors[0]) == 'commerce.error.stale'
    assert Order.objects.count() == OrderLine.objects.count() == ReservationLine.objects.count() == 1
    assert InventoryMovement.objects.filter(source='checkout_test').count() == 1
    assert_conserved(variants)


def test_checkout_and_staff_reserve_share_the_same_last_unit_lock(records):
    actor, variants = records
    client = Client()
    token = prepare(client, variants[:1])
    request = request_snapshot(client)
    now = timezone.now()
    results = race([lambda: create_test_order(request, token),
        lambda: services.reserve(actor=actor, variant_id=variants[0].pk, reservation_id='staff-race', quantity=1,
            context=OperationContext('staff-race', 'staff', str(actor.pk), 'QA reserve', 1),
            expires_at=now + timedelta(minutes=30), now=now)])
    assert sum(isinstance(result, (CartError, StaleRevisionError)) for result in results) == 1
    assert ReservationLine.objects.count() == 1
    assert_conserved(variants)


def test_late_audit_failure_rolls_back_order_and_all_sku_holds(records):
    _, variants = records
    client = Client()
    token = prepare(client, variants)
    request = request_snapshot(client)
    create_audit = StaffAuditEvent.objects.create
    calls = []

    def audit(**kwargs):
        calls.append(kwargs)
        if len(calls) == 2:
            raise RuntimeError('injected late audit failure')
        return create_audit(**kwargs)

    with patch('web.inventory.reservation_persistence.StaffAuditEvent.objects.create', side_effect=audit):
        with pytest.raises(RuntimeError, match='injected late audit failure'):
            create_test_order(request, token)
    assert not Order.objects.exists() and not OrderLine.objects.exists() and not ReservationLine.objects.exists()
    assert not InventoryMovement.objects.filter(source='checkout_test').exists()
    assert client.session['local_cart_guest'] == {variant.sku: 1 for variant in variants}
    assert_conserved(variants)


def test_expiry_commits_before_failed_checkout_and_old_successful_replay_never_reholds(records):
    actor, variants = records
    client = Client()
    token = prepare(client, variants[:1])
    order = create_test_order(request_snapshot(client), token)
    original_deadline = order.inventory_hold_expires_at
    assert expire_due_reservations(actor=actor, now=original_deadline).expired == 1
    new_token = prepare(client, variants[1:])
    before = dict(client.session)
    replay = create_test_order(request_snapshot(client), token)
    assert replay.pk == order.pk and replay.inventory_hold_expires_at == original_deadline
    assert dict(client.session) == before and token != new_token
    assert Order.objects.count() == ReservationLine.objects.count() == 1
    assert ReservationLine.objects.get().state == 'closed'
    assert_conserved(variants)
