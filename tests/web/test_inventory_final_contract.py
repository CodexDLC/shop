from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from codex_ecommerce.inventory import (
    IdempotencyConflictError,
    InvalidQuantityError,
    InvalidTransitionError,
    InventoryInvariantError,
    OperationContext,
    StaleRevisionError,
)
from web.catalog.models import Brand, Category, Product, ProductVariant
from web.inventory import selectors, services
from web.inventory.expiry_backlog_error import ExpiryBacklogError
from web.inventory.expiry_transaction_error import ExpiryTransactionError
from web.inventory.fake_source_fact import FakeSourceFact
from web.inventory.fake_source_service import ingest_fake_fact
from web.inventory.models import (
    ExternalInventoryConflict,
    ExternalInventoryReceipt,
    InventoryChangeEvent,
    InventoryMovement,
    ReservationLine,
    StockBalance,
)
from web.inventory.snapshots import decode_reservation, encode_reservation
from web.inventory.write_access import service_write
from web.orders.models import Order, OrderLine
from web.staff.inventory_workspace.selectors import reconciliation
from web.staff.models import StaffAuditEvent

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 11, 5, 12, tzinfo=UTC)


@pytest.fixture
def records(request):
    actor = get_user_model().objects.create_user(username='final-contract', is_staff=True, is_superuser=True)
    brand = Brand.objects.create(slug='final', name='Brand')
    category = Category.objects.create(slug='final', name_key='category')
    product = Product.objects.create(slug='final', model_name='Product', brand=brand, category=category)
    variant = ProductVariant.objects.create(product=product, sku='FINAL-1', color_code='black',
        color_name_key='black', size='M', price='10.00')
    services.initialize(actor=actor, variant_id=variant.pk, quantity=getattr(request, 'param', 3), context=ctx(actor, 'init', 0))
    return actor, variant


def ctx(actor, key, revision):
    return OperationContext(key, 'staff', str(actor.pk), 'Isolated final contract QA', revision)


def shipped(actor, variant):
    held = services.reserve(actor=actor, variant_id=variant.pk, reservation_id='test-shipped', quantity=2,
        context=ctx(actor, 'hold', 1), now=NOW, expires_at=NOW + timedelta(minutes=30))
    committed = services.commit(actor=actor, variant_id=variant.pk, reservation_id='test-shipped',
        context=ctx(actor, 'commit', held.stock.revision), expected_reservation_revision=1, now=NOW)
    return services.fulfill(actor=actor, variant_id=variant.pk, reservation_id='test-shipped', quantity=2,
        context=ctx(actor, 'fulfill', committed.stock.revision), expected_reservation_revision=2, now=NOW)


def returned(actor, variant, previous, key='return', quantity=1):
    return services.checked_return(actor=actor, variant_id=variant.pk, reservation_id='test-shipped', quantity=quantity,
        context=ctx(actor, key, previous.stock.revision), expected_reservation_revision=previous.reservation.revision,
        now=NOW, received=True, inspected=True)


def test_return_replay_cap_history_and_event(records):
    actor, variant = records
    previous = shipped(actor, variant)
    result = returned(actor, variant, previous)
    assert returned(actor, variant, previous) == result
    assert result.reservation.returned == 1 and result.reservation.consumed == 2
    assert result.stock.on_hand == 2 and result.stock.reserved == 0
    with pytest.raises(InvalidQuantityError):
        returned(actor, variant, result, key='excess', quantity=2)
    assert InventoryChangeEvent.objects.count() == InventoryMovement.objects.count() == StaffAuditEvent.objects.count() == 5
    events = selectors.change_events(actor=actor, after_id=0, limit=2)
    assert len(events) == 2
    assert all('reason' not in event.payload() and 'actor' not in event.payload() for event in events)
    assert len(selectors.change_events(actor=actor, after_id=events[-1].cursor, limit=100)) == 3


@pytest.mark.parametrize('operation', ['accounting', 'return'])
def test_event_insert_failure_rolls_back_every_effect(records, operation):
    actor, variant = records
    previous = shipped(actor, variant) if operation == 'return' else None
    before = selectors.stock(actor=actor, variant_id=variant.pk)
    count = InventoryMovement.objects.count()
    with patch('web.inventory.models.inventory_change_event.InventoryChangeEvent.objects.create', side_effect=RuntimeError('event failure')):
        with pytest.raises(RuntimeError):
            if operation == 'return':
                returned(actor, variant, previous)
            else:
                services.receive(actor=actor, variant_id=variant.pk, quantity=1, context=ctx(actor, 'receive', 1))
    assert selectors.stock(actor=actor, variant_id=variant.pk) == before
    assert InventoryMovement.objects.count() == InventoryChangeEvent.objects.count() == StaffAuditEvent.objects.count() == count
    if previous:
        assert selectors.reservation(actor=actor, reservation_id='test-shipped') == previous.reservation


def test_fake_source_duplicate_stale_pending_and_shortage_are_persisted(records, settings):
    actor, variant = records
    fact = FakeSourceFact('synthetic-sale-1', variant.pk, 'completed_sale', 1, 1)
    with pytest.raises(PermissionDenied):
        ingest_fake_fact(actor=actor, fact=fact, now=NOW)
    settings.SHOP_CHECKOUT_STOCK_MODE = 'inventory_test'
    first = ingest_fake_fact(actor=actor, fact=fact, now=NOW)
    assert first.status == 'applied' and (first.stock.on_hand, first.stock.reserved) == (3, 1)
    assert ingest_fake_fact(actor=actor, fact=fact, now=NOW + timedelta(days=1)) == first
    with pytest.raises(IdempotencyConflictError):
        ingest_fake_fact(actor=actor, fact=FakeSourceFact(fact.external_id, variant.pk, 'completed_sale', 2, 1), now=NOW)
    assert ExternalInventoryConflict.objects.count() == 1
    # This snapshot observed local revision1 before the synthetic sale; never overwrite it.
    stale = ingest_fake_fact(actor=actor, fact=FakeSourceFact('synthetic-snapshot-1', variant.pk, 'snapshot', 9, 2, 1), now=NOW)
    assert stale.status == 'stale_snapshot' and (stale.stock.on_hand, stale.stock.reserved) == (3, 1)
    shortage = ingest_fake_fact(actor=actor, fact=FakeSourceFact('synthetic-sale-2', variant.pk, 'completed_sale', 3, 3), now=NOW)
    assert shortage.status == 'needs_attention' and shortage.stock.on_hand == 3
    assert ExternalInventoryReceipt.objects.count() == 3
    assert InventoryMovement.objects.count() == InventoryChangeEvent.objects.count() == 3


def test_return_attestations_permissions_stale_and_inactive_variant(records):
    actor, variant = records
    previous = shipped(actor, variant)
    variant.is_active = False
    variant.save()
    result = returned(actor, variant, previous)
    movement = InventoryMovement.objects.get(kind='checked_return')
    assert movement.received is True and movement.inspected is True
    with pytest.raises(InvalidTransitionError):
        services.checked_return(actor=actor, variant_id=variant.pk, reservation_id='test-shipped', quantity=1,
            context=ctx(actor, 'return', previous.stock.revision), expected_reservation_revision=previous.reservation.revision,
            now=NOW, received=True, inspected=False)
    with pytest.raises(StaleRevisionError):
        returned(actor, variant, previous, key='stale')
    readonly = get_user_model().objects.create_user(username='readonly-return', is_staff=True)
    readonly.user_permissions.add(Permission.objects.get(codename='fulfill_reservationline'))
    with pytest.raises(PermissionDenied):
        returned(readonly, variant, result)
    readonly.user_permissions.add(Permission.objects.get(codename='checked_return_reservationline'))
    assert returned(readonly, variant, result, key='authorized').reservation.returned == 2
    actor.is_active = False
    actor.save()
    with pytest.raises(PermissionDenied):
        returned(actor, variant, previous)


def test_old_snapshots_explicitly_decode_zero_and_new_snapshots_keep_counter(records):
    actor, variant = records
    previous = shipped(actor, variant)
    encoded = encode_reservation(previous.reservation)
    assert encoded.pop('returned') == 0
    assert decode_reservation(encoded) == previous.reservation
    encoded['extra'] = 1
    with pytest.raises(InventoryInvariantError):
        decode_reservation(encoded)
    result = returned(actor, variant, previous)
    assert decode_reservation(encode_reservation(result.reservation)) == result.reservation
    # A pre-migration movement JSON remains a valid immutable replay. No rewrite is required.
    old_movement = InventoryMovement.objects.get(kind='fulfill')
    before, after = dict(old_movement.before_reservation), dict(old_movement.after_reservation)
    before.pop('returned')
    after.pop('returned')
    old_movement.before_reservation, old_movement.after_reservation = before, after
    from web.inventory.snapshots import movement_snapshot
    assert movement_snapshot(old_movement) == previous


@pytest.mark.parametrize('operation', ['reserve', 'commit', 'release', 'fulfill'])
def test_event_failure_rolls_back_each_reservation_transition(records, operation):
    actor, variant = records
    if operation == 'reserve':
        before_line = None
    else:
        held = services.reserve(actor=actor, variant_id=variant.pk, reservation_id='event-line', quantity=2,
            context=ctx(actor, 'hold', 1), expires_at=NOW + timedelta(minutes=30), now=NOW)
        before_line = held.reservation
        if operation == 'fulfill':
            before_line = services.commit(actor=actor, variant_id=variant.pk, reservation_id='event-line',
                context=ctx(actor, 'commit', 2), expected_reservation_revision=1, now=NOW).reservation
    before = selectors.stock(actor=actor, variant_id=variant.pk)
    count = InventoryMovement.objects.count()
    args = dict(actor=actor, variant_id=variant.pk, reservation_id='event-line', context=ctx(actor, 'failed', before.revision), now=NOW)
    if operation == 'reserve':
        args.update(quantity=2, expires_at=NOW + timedelta(minutes=30))
    else:
        args['expected_reservation_revision'] = before_line.revision
        if operation != 'commit':
            args['quantity'] = 1
    with patch.object(InventoryChangeEvent.objects, 'create', side_effect=RuntimeError('event failure')):
        with pytest.raises(RuntimeError):
            getattr(services, operation)(**args)
    assert selectors.stock(actor=actor, variant_id=variant.pk) == before
    assert selectors.reservation(actor=actor, reservation_id='event-line') == before_line
    assert InventoryMovement.objects.count() == InventoryChangeEvent.objects.count() == StaffAuditEvent.objects.count() == count


def test_caught_event_failure_cannot_leave_orphan_trusted_movement(records):
    actor, _ = records
    original = InventoryMovement.objects.get()
    values = {field.attname: getattr(original, field.attname) for field in InventoryMovement._meta.fields
        if field.name not in ('id', 'created_at')}
    values.update(operation_key='trusted-failed-insert', revision=2)
    with transaction.atomic(), service_write():
        with patch.object(InventoryChangeEvent.objects, 'create', side_effect=RuntimeError('event failure')):
            with pytest.raises(RuntimeError):
                InventoryMovement.objects.create(**values)
    assert InventoryMovement.objects.count() == InventoryChangeEvent.objects.count() == 1
    # A process crash after commit and before enqueue does not erase this journal.
    result = services.receive(actor=actor, variant_id=original.variant_id, quantity=1, context=ctx(actor, 'committed', 1))
    try:
        raise RuntimeError('simulated process stop before enqueue')
    except RuntimeError:
        pass
    event = InventoryChangeEvent.objects.order_by('-pk').first()
    assert event.snapshot().stock == result


def test_journals_append_only_and_read_permissions_and_query_bounds(records, settings):
    actor, variant = records
    settings.SHOP_CHECKOUT_STOCK_MODE = 'inventory_test'
    ingest_fake_fact(actor=actor, fact=FakeSourceFact('journal-sale', variant.pk, 'completed_sale', 1, 1), now=NOW)
    for model in (InventoryChangeEvent, ExternalInventoryReceipt):
        row = model.objects.first()
        with service_write(), pytest.raises(PermissionDenied):
            row.save()
        with pytest.raises(PermissionDenied):
            row.delete()
        for action in (lambda: model.objects.all().update(id=99), lambda: model.objects.all().delete(),
                lambda: model.objects.bulk_create([]), lambda: model.objects.bulk_update([], ['id'])):
            with service_write(), pytest.raises(PermissionDenied):
                action()
    for reader in (selectors.change_events, selectors.fake_receipts):
        for bad in (0, 101, True, -1):
            with pytest.raises(InventoryInvariantError):
                reader(actor=actor, limit=bad)
        with pytest.raises(InventoryInvariantError):
            reader(actor=actor, after_id=True)
        with pytest.raises(PermissionDenied):
            reader(actor=AnonymousUser())
        for limit in (1, 100):
            with CaptureQueriesContext(connection) as queries:
                reader(actor=actor, limit=limit)
            # One active staff reload, one bounded data query; no joins/lazy fetches.
            assert len(queries) == 2


def test_fake_snapshot_fences_source_and_pending_local_movements(records, settings):
    actor, variant = records
    settings.SHOP_CHECKOUT_STOCK_MODE = 'inventory_test'
    services.receive(actor=actor, variant_id=variant.pk, quantity=2, context=ctx(actor, 'local-receive', 1))
    stale = ingest_fake_fact(actor=actor, fact=FakeSourceFact('pending-receive', variant.pk, 'snapshot', 1, 1, 1), now=NOW)
    assert stale.status == 'stale_snapshot' and stale.code == 'local_revision_changed' and stale.stock.on_hand == 5
    hold = services.reserve(actor=actor, variant_id=variant.pk, reservation_id='local-pending', quantity=2,
        context=ctx(actor, 'local-hold', 2), expires_at=NOW + timedelta(minutes=30), now=NOW)
    stale = ingest_fake_fact(actor=actor, fact=FakeSourceFact('pending-hold', variant.pk, 'snapshot', 1, 2, 2), now=NOW)
    assert stale.status == 'stale_snapshot' and stale.stock == hold.stock
    below = ingest_fake_fact(actor=actor, fact=FakeSourceFact('below-reserved', variant.pk, 'snapshot', 1, 3, 3), now=NOW)
    assert below.status == 'needs_attention' and below.code == 'below_local_reservations'
    accepted = ingest_fake_fact(actor=actor, fact=FakeSourceFact('fresh-snapshot', variant.pk, 'snapshot', 6, 5, 3), now=NOW)
    assert accepted.status == 'applied' and (accepted.stock.on_hand, accepted.stock.reserved) == (6, 2)
    old = ingest_fake_fact(actor=actor, fact=FakeSourceFact('older-source', variant.pk, 'snapshot', 4, 4, 4), now=NOW)
    assert old.status == 'stale_snapshot' and old.code == 'source_revision_changed'
    assert selectors.stock(actor=actor, variant_id=variant.pk) == accepted.stock
    assert reconciliation(variant.pk)['matches']


def test_fake_sale_shortage_is_not_retried_implicitly_after_stock_changes(records, settings):
    actor, variant = records
    settings.SHOP_CHECKOUT_STOCK_MODE = 'inventory_test'
    services.reserve(actor=actor, variant_id=variant.pk, reservation_id='promised', quantity=3,
        context=ctx(actor, 'promise', 1), expires_at=NOW + timedelta(minutes=30), now=NOW)
    fact = FakeSourceFact('shortage-fact', variant.pk, 'completed_sale', 1, 1)
    shortage = ingest_fake_fact(actor=actor, fact=fact, now=NOW)
    assert shortage.status == 'needs_attention' and shortage.reservation_id is None
    services.receive(actor=actor, variant_id=variant.pk, quantity=1, context=ctx(actor, 'extra', 2), now=NOW)
    assert ingest_fake_fact(actor=actor, fact=fact, now=NOW) == shortage
    assert StockBalance.objects.get(variant=variant).reserved == 3
    assert ExternalInventoryReceipt.objects.count() == 1


@pytest.mark.parametrize('invalid_actor', ['anonymous', 'nonstaff', 'inactive', 'missing_permission'])
def test_synthetic_source_requires_native_persisted_staff_permission(records, settings, invalid_actor):
    actor, variant = records
    settings.SHOP_CHECKOUT_STOCK_MODE = 'inventory_test'
    if invalid_actor == 'anonymous':
        actor = AnonymousUser()
    elif invalid_actor == 'missing_permission':
        actor = get_user_model().objects.create_user(username='no-source-right', is_staff=True)
    else:
        setattr(actor, 'is_staff' if invalid_actor == 'nonstaff' else 'is_active', False)
        actor.save()
    with pytest.raises(PermissionDenied):
        ingest_fake_fact(actor=actor, fact=FakeSourceFact('blocked', variant.pk, 'completed_sale', 1, 1), now=NOW)
    assert ExternalInventoryReceipt.objects.count() == 0


def test_synthetic_sale_committed_until_explicit_fulfillment_and_return(records, settings):
    actor, variant = records
    settings.SHOP_CHECKOUT_STOCK_MODE = 'inventory_test'
    result = ingest_fake_fact(actor=actor, fact=FakeSourceFact('external-obligation', variant.pk, 'completed_sale', 2, 1), now=NOW)
    line = selectors.reservation(actor=actor, reservation_id=result.reservation_id)
    assert line.state.value == 'committed' and line.expires_at is None
    assert (result.stock.on_hand, result.stock.reserved, result.stock.revision) == (3, 2, 3)
    assert [row.kind for row in InventoryMovement.objects.order_by('pk')] == ['initialize', 'reserve', 'commit']
    shipped_result = services.fulfill(actor=actor, variant_id=variant.pk, reservation_id=line.reservation_id,
        quantity=2, context=ctx(actor, 'explicit-ship', 3), expected_reservation_revision=line.revision, now=NOW)
    assert shipped_result.stock.on_hand == 1 and shipped_result.stock.reserved == 0
    accepted = services.checked_return(actor=actor, variant_id=variant.pk, reservation_id=line.reservation_id,
        quantity=1, context=ctx(actor, 'explicit-return', 4), expected_reservation_revision=3, now=NOW,
        received=True, inspected=True)
    assert accepted.stock.on_hand == 2 and accepted.reservation.consumed == 2 and accepted.reservation.returned == 1
    assert reconciliation(variant.pk)['matches']


@pytest.mark.parametrize('failure', ['event', 'receipt', 'audit'])
def test_synthetic_failure_rolls_back_fact_stock_reservation_movements_events_and_audit(records, settings, failure):
    actor, variant = records
    settings.SHOP_CHECKOUT_STOCK_MODE = 'inventory_test'
    model = {'event': InventoryChangeEvent, 'receipt': ExternalInventoryReceipt, 'audit': StaffAuditEvent}[failure]
    with patch.object(model.objects, 'create', side_effect=RuntimeError('late failure')):
        with pytest.raises(RuntimeError):
            ingest_fake_fact(actor=actor, fact=FakeSourceFact('failed-source', variant.pk, 'completed_sale', 2, 1), now=NOW)
    assert (StockBalance.objects.get().on_hand, StockBalance.objects.get().reserved) == (3, 0)
    assert ReservationLine.objects.count() == ExternalInventoryReceipt.objects.count() == 0
    assert InventoryMovement.objects.count() == InventoryChangeEvent.objects.count() == StaffAuditEvent.objects.count() == 1


def prepare_checkout(client, variant):
    """Native HTTP fixture helper, also usable from an isolated pytest --trace session."""
    assert client.post(reverse('cart:add'), {'sku': variant.sku, 'quantity': 1}).status_code == 302
    address = dict(email='isolated@example.test', first_name='QA', last_name='Test', street='Testweg 1',
        postal_code='10115', city='Berlin', country='DE')
    assert client.post(reverse('orders:address'), address).status_code == 302
    return client.get(reverse('payments:review')).context['checkout_token']


def submit_checkout(client, token):
    return client.post(reverse('payments:review'), {'method': 'test', 'checkout_token': token})


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('records', [0], indirect=True)
def test_full_receipt_two_ab_c_shortage_release_a_d_ship_b_repeat(records, settings):
    """Original INV scenario traverses native cart, checkout and the shared warehouse."""
    actor, variant = records
    settings.SHOP_CHECKOUT_STOCK_MODE = 'inventory_test'
    now = timezone.now()
    services.receive(actor=actor, variant_id=variant.pk, quantity=2, context=ctx(actor, 'receipt-two', 1), now=now)
    a, b, c, d = Client(), Client(), Client(), Client()
    tokens = {name: prepare_checkout(client, variant) for name, client in [('a', a), ('b', b), ('c', c)]}
    assert submit_checkout(a, tokens['a']).status_code == submit_checkout(b, tokens['b']).status_code == 302
    lines = list(ReservationLine.objects.select_related('order_line').order_by('created_at', 'reference'))
    line_a, line_b = lines
    assert (StockBalance.objects.get().on_hand, StockBalance.objects.get().reserved) == (2, 2)
    before_c = dict(c.session)
    assert submit_checkout(c, tokens['c']).status_code == 409
    assert c.session['local_cart_guest'] == before_c['local_cart_guest']
    assert Order.objects.count() == OrderLine.objects.count() == 2
    assert c.get(reverse('cart:detail')).context['cart']['errors']
    assert c.get(reverse('catalog:detail', kwargs={'slug': variant.product.slug})).status_code == 200
    pdp = c.get(reverse('catalog:detail', kwargs={'slug': variant.product.slug}))
    assert not pdp.context['product']['variants'][0]['available']
    from django.http import QueryDict

    from web.catalog.listing_context import ListingContext
    from web.catalog.listing_request import ListingRequest
    assert ListingContext(ListingRequest.from_query(QueryDict('in_stock=1'))).build()['total'] == 0
    release_a = services.release(actor=actor, variant_id=variant.pk, reservation_id=line_a.reference, quantity=1,
        context=ctx(actor, 'release-a', 4), expected_reservation_revision=line_a.revision, now=now)
    assert release_a.stock.available == 1
    assert ListingContext(ListingRequest.from_query(QueryDict('in_stock=1'))).build()['total'] == 1
    token_d = prepare_checkout(d, variant)
    assert submit_checkout(d, token_d).status_code == 302
    committed_b = services.commit(actor=actor, variant_id=variant.pk, reservation_id=line_b.reference,
        context=ctx(actor, 'test-commit-b', 6), expected_reservation_revision=line_b.revision, now=now)
    fulfilled_b = services.fulfill(actor=actor, variant_id=variant.pk, reservation_id=line_b.reference, quantity=1,
        context=ctx(actor, 'test-ship-b', 7), expected_reservation_revision=committed_b.reservation.revision, now=now)
    assert (fulfilled_b.stock.on_hand, fulfilled_b.stock.reserved, fulfilled_b.stock.available) == (1, 1, 0)
    assert services.fulfill(actor=actor, variant_id=variant.pk, reservation_id=line_b.reference, quantity=1,
        context=ctx(actor, 'test-ship-b', 7), expected_reservation_revision=committed_b.reservation.revision, now=now) == fulfilled_b
    assert submit_checkout(b, tokens['b']).status_code == 302
    assert Order.objects.count() == 3 and InventoryMovement.objects.count() == InventoryChangeEvent.objects.count() == 8
    assert reconciliation(variant.pk)['matches']


@pytest.mark.django_db(transaction=True)
def test_expiry_event_failure_rolls_back_line_balance_history_audit(records):
    from web.inventory.expiry_service import expire_due_reservations

    actor, variant = records
    services.reserve(actor=actor, variant_id=variant.pk, reservation_id='due-event', quantity=2,
        context=ctx(actor, 'due-hold', 1), now=NOW, expires_at=NOW + timedelta(seconds=1))
    with patch.object(InventoryChangeEvent.objects, 'create', side_effect=RuntimeError('event failure')):
        with pytest.raises(RuntimeError):
            expire_due_reservations(actor=actor, now=NOW + timedelta(seconds=1), batch_size=1)
    assert StockBalance.objects.get().reserved == 2 and ReservationLine.objects.get().state == 'held'
    assert InventoryMovement.objects.count() == InventoryChangeEvent.objects.count() == StaffAuditEvent.objects.count() == 2


@pytest.mark.django_db(transaction=True)
def test_checkout_event_failure_rolls_back_order_and_keeps_native_cart(records, settings):
    actor, variant = records
    settings.SHOP_CHECKOUT_STOCK_MODE = 'inventory_test'
    second = ProductVariant.objects.create(product=variant.product, sku='FINAL-MULTI', color_code='black',
        color_name_key='black', size='L', price='10.00')
    services.initialize(actor=actor, variant_id=second.pk, quantity=3, context=ctx(actor, 'init-second', 0))
    buyer = Client()
    prepare_checkout(buyer, variant)
    token = prepare_checkout(buyer, second)
    before = dict(buyer.session)
    original_create, calls = InventoryChangeEvent.objects.create, []

    def fail_second_event(**kwargs):
        calls.append(kwargs)
        if len(calls) == 2:
            raise RuntimeError('second SKU event failure')
        return original_create(**kwargs)

    with patch.object(InventoryChangeEvent.objects, 'create', side_effect=fail_second_event):
        with pytest.raises(RuntimeError):
            submit_checkout(buyer, token)
    assert Order.objects.count() == OrderLine.objects.count() == ReservationLine.objects.count() == 0
    assert all(balance.reserved == 0 for balance in StockBalance.objects.all())
    assert InventoryMovement.objects.count() == InventoryChangeEvent.objects.count() == StaffAuditEvent.objects.count() == 2
    assert buyer.session['local_cart_guest'] == before['local_cart_guest']


def test_return_partial_shipment_keeps_remaining_obligation_and_overflow_rolls_back(records):
    actor, variant = records
    services.reserve(actor=actor, variant_id=variant.pk, reservation_id='test-shipped', quantity=2,
        context=ctx(actor, 'hold', 1), now=NOW, expires_at=NOW + timedelta(minutes=30))
    services.commit(actor=actor, variant_id=variant.pk, reservation_id='test-shipped', context=ctx(actor, 'commit', 2),
        expected_reservation_revision=1, now=NOW)
    partial = services.fulfill(actor=actor, variant_id=variant.pk, reservation_id='test-shipped', quantity=1,
        context=ctx(actor, 'partial', 3), expected_reservation_revision=2, now=NOW)
    result = returned(actor, variant, partial)
    assert (result.stock.on_hand, result.stock.reserved) == (3, 1)
    assert (result.reservation.state.value, result.reservation.remaining_reserved, result.reservation.returned) == ('committed', 1, 1)
    rest = services.fulfill(actor=actor, variant_id=variant.pk, reservation_id='test-shipped', quantity=1,
        context=ctx(actor, 'rest-shipped', 5), expected_reservation_revision=4, now=NOW)
    maximum = 9223372036854775807
    services.adjust(actor=actor, variant_id=variant.pk, quantity=maximum, context=ctx(actor, 'max', 6), now=NOW)
    count = InventoryMovement.objects.count()
    with pytest.raises(InvalidQuantityError):
        services.checked_return(actor=actor, variant_id=variant.pk, reservation_id='test-shipped', quantity=1,
            context=ctx(actor, 'overflow-return', 7), expected_reservation_revision=rest.reservation.revision,
            now=NOW, received=True, inspected=True)
    assert StockBalance.objects.get().on_hand == maximum
    assert ReservationLine.objects.get().returned == 1
    assert InventoryMovement.objects.count() == InventoryChangeEvent.objects.count() == count


@pytest.mark.django_db(transaction=True)
def test_synthetic_ingestion_cleans_stopped_worker_holds_with_ingest_only_permission(records, settings):
    actor, variant = records
    settings.SHOP_CHECKOUT_STOCK_MODE = 'inventory_test'
    services.reserve(actor=actor, variant_id=variant.pk, reservation_id='expired-local', quantity=3,
        context=ctx(actor, 'hold-expired', 1), now=NOW, expires_at=NOW + timedelta(seconds=1))
    ingester = get_user_model().objects.create_user(username='ingest-only', is_staff=True)
    ingester.user_permissions.add(Permission.objects.get(codename='ingest_fake_inventory'))
    assert not ingester.has_perm('inventory.expire_reservationline')
    result = ingest_fake_fact(actor=ingester,
        fact=FakeSourceFact('after-stopped-worker', variant.pk, 'completed_sale', 1, 1),
        now=NOW + timedelta(seconds=1))
    assert result.status == 'applied' and (result.stock.on_hand, result.stock.reserved) == (3, 1)
    assert ReservationLine.objects.get(reference='expired-local').state == 'closed'
    assert ReservationLine.objects.get(reference=result.reservation_id).state == 'committed'
    assert InventoryMovement.objects.filter(kind='expire').count() == 1
    assert InventoryMovement.objects.count() == InventoryChangeEvent.objects.count() == StaffAuditEvent.objects.count() == 5
    assert reconciliation(variant.pk)['matches']


@pytest.mark.django_db(transaction=True)
def test_synthetic_ingestion_backlog_is_bounded_and_does_not_claim_fact(records, settings):
    actor, variant = records
    settings.SHOP_CHECKOUT_STOCK_MODE = 'inventory_test'
    services.adjust(actor=actor, variant_id=variant.pk, quantity=21, context=ctx(actor, 'larger', 1), now=NOW)
    for index in range(21):
        services.reserve(actor=actor, variant_id=variant.pk, reservation_id=f'backlog-{index}', quantity=1,
            context=ctx(actor, f'backlog-hold-{index}', 2 + index), now=NOW, expires_at=NOW + timedelta(seconds=1))
    fact = FakeSourceFact('after-backlog', variant.pk, 'completed_sale', 1, 1)
    with pytest.raises(ExpiryBacklogError):
        ingest_fake_fact(actor=actor, fact=fact, now=NOW + timedelta(seconds=1))
    assert ExternalInventoryReceipt.objects.count() == 0
    assert InventoryMovement.objects.filter(kind='expire').count() == 20
    assert StockBalance.objects.get().reserved == 1
    result = ingest_fake_fact(actor=actor, fact=fact, now=NOW + timedelta(seconds=1))
    assert result.status == 'applied' and result.stock.reserved == 1
    assert InventoryMovement.objects.filter(kind='expire').count() == 21
    assert ExternalInventoryReceipt.objects.count() == 1
    assert reconciliation(variant.pk)['matches']


def test_synthetic_ingestion_due_cleanup_requires_autocommit_before_new_receipt(records, settings):
    actor, variant = records
    settings.SHOP_CHECKOUT_STOCK_MODE = 'inventory_test'
    services.reserve(actor=actor, variant_id=variant.pk, reservation_id='outer-due', quantity=3,
        context=ctx(actor, 'outer-held', 1), now=NOW, expires_at=NOW + timedelta(seconds=1))
    with pytest.raises(ExpiryTransactionError):
        ingest_fake_fact(actor=actor, fact=FakeSourceFact('outer-fact', variant.pk, 'completed_sale', 1, 1),
            now=NOW + timedelta(seconds=1))
    assert ExternalInventoryReceipt.objects.count() == 0
    assert StockBalance.objects.get().reserved == 3
    assert ReservationLine.objects.get().state == 'held'
    assert InventoryMovement.objects.count() == InventoryChangeEvent.objects.count() == 2


def test_synthetic_replay_and_conflict_precede_cleanup_with_constant_read_budget(records, settings):
    actor, variant = records
    settings.SHOP_CHECKOUT_STOCK_MODE = 'inventory_test'
    fact = FakeSourceFact('already-recorded', variant.pk, 'completed_sale', 1, 1)
    original = ingest_fake_fact(actor=actor, fact=fact, now=NOW)
    services.reserve(actor=actor, variant_id=variant.pk, reservation_id='later-due', quantity=2,
        context=ctx(actor, 'later-held', original.stock.revision), now=NOW, expires_at=NOW + timedelta(seconds=1))
    with patch('web.inventory.fake_source_service.opportunistic_cleanup', side_effect=AssertionError('replay must not cleanup')):
        with CaptureQueriesContext(connection) as queries:
            assert ingest_fake_fact(actor=actor, fact=fact, now=NOW + timedelta(seconds=1)) == original
        assert len(queries) == 2
        assert not any('inventory_reservationline' in row['sql'].lower() for row in queries)
        with pytest.raises(IdempotencyConflictError):
            ingest_fake_fact(actor=actor, fact=FakeSourceFact(fact.external_id, variant.pk, 'completed_sale', 2, 1),
                now=NOW + timedelta(seconds=1))
    assert ExternalInventoryConflict.objects.count() == 1
    assert ReservationLine.objects.get(reference='later-due').state == 'held'
    assert InventoryMovement.objects.filter(kind='expire').count() == 0


@pytest.mark.django_db(transaction=True)
def test_synthetic_locked_due_recheck_does_not_store_false_shortage(records, settings):
    actor, variant = records
    settings.SHOP_CHECKOUT_STOCK_MODE = 'inventory_test'

    def concurrent_new_due(**kwargs):
        # A command can appear after the preflight scan. Under-lock recheck
        # must abort instead of persisting a false shortage for this fact.
        services.reserve(actor=actor, variant_id=variant.pk, reservation_id='new-due', quantity=3,
            context=ctx(actor, 'new-due-hold', 1), now=NOW, expires_at=NOW + timedelta(seconds=1))

    with patch('web.inventory.fake_source_service.opportunistic_cleanup', side_effect=concurrent_new_due):
        with pytest.raises(ExpiryBacklogError):
            ingest_fake_fact(actor=actor, fact=FakeSourceFact('new-due-fact', variant.pk, 'completed_sale', 1, 1),
                now=NOW + timedelta(seconds=1))
    assert ExternalInventoryReceipt.objects.count() == 0
    assert StockBalance.objects.get().reserved == 3
