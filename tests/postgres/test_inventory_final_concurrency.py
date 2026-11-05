from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, Event
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection

from codex_ecommerce.inventory import (
    IdempotencyConflictError,
    InvalidQuantityError,
    InventoryError,
    OperationContext,
    ReservationResult,
    StaleRevisionError,
)
from web.catalog.models import Brand, Category, Product, ProductVariant
from web.inventory import services
from web.inventory.expiry_backlog_error import ExpiryBacklogError
from web.inventory.expiry_service import opportunistic_cleanup
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
from web.staff.inventory_workspace.selectors import reconciliation

pytestmark = [pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != 'postgresql', reason='Requires isolated PostgreSQL test database')]
NOW = datetime(2026, 11, 5, 12, tzinfo=UTC)


@pytest.fixture
def records(settings):
    settings.SHOP_CHECKOUT_STOCK_MODE = 'inventory_test'
    actor = get_user_model().objects.create_user(username='final-race', is_staff=True, is_superuser=True)
    brand = Brand.objects.create(slug='final-race', name='Brand')
    category = Category.objects.create(slug='final-race', name_key='category')
    product = Product.objects.create(slug='final-race', model_name='Product', brand=brand, category=category)
    variants = [ProductVariant.objects.create(product=product, sku=f'FINAL-RACE-{i}', color_code='black',
        color_name_key='black', size=str(i), price='10.00') for i in range(2)]
    for variant in variants:
        services.initialize(actor=actor, variant_id=variant.pk, quantity=3, context=ctx(actor, f'init-{variant.pk}', 0))
    return actor, variants


def ctx(actor, key, revision):
    return OperationContext(key, 'staff', str(actor.pk), 'Isolated final concurrency QA', revision)


def race(functions):
    barrier = Barrier(len(functions))

    def run(function):
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '5s'")
                cursor.execute("SET statement_timeout = '10s'")
                cursor.execute('SELECT pg_backend_pid()')
                backend = cursor.fetchone()[0]
            barrier.wait(timeout=10)
            try:
                return backend, function()
            except InventoryError as error:
                return backend, error
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=len(functions)) as executor:
        futures = [executor.submit(run, function) for function in functions]
        results = [future.result(timeout=25) for future in futures]
    assert len({backend for backend, _ in results}) == len(functions)
    return [result for _, result in results]


def shipped(actor, variant):
    services.reserve(actor=actor, variant_id=variant.pk, reservation_id='shipped', quantity=2,
        context=ctx(actor, 'hold', 1), now=NOW, expires_at=NOW + timedelta(minutes=30))
    services.commit(actor=actor, variant_id=variant.pk, reservation_id='shipped', context=ctx(actor, 'commit', 2),
        expected_reservation_revision=1, now=NOW)
    return services.fulfill(actor=actor, variant_id=variant.pk, reservation_id='shipped', quantity=2,
        context=ctx(actor, 'ship', 3), expected_reservation_revision=2, now=NOW)


def accept_return(actor, variant, previous, key, quantity=2):
    return services.checked_return(actor=actor, variant_id=variant.pk, reservation_id='shipped', quantity=quantity,
        context=ctx(actor, key, previous.stock.revision), expected_reservation_revision=previous.reservation.revision,
        now=NOW, received=True, inspected=True)


def test_competing_returns_cas_then_cap_prevents_double_restock(records):
    actor, (variant, _) = records
    previous = shipped(actor, variant)
    results = race([lambda: accept_return(actor, variant, previous, 'return-a'),
        lambda: accept_return(actor, variant, previous, 'return-b')])
    assert sum(isinstance(result, StaleRevisionError) for result in results) == 1
    winner = next(result for result in results if isinstance(result, ReservationResult))
    with pytest.raises(InvalidQuantityError):
        accept_return(actor, variant, winner, 'over-return', quantity=1)
    assert StockBalance.objects.get(variant=variant).on_hand == 3
    assert ReservationLine.objects.get().returned == ReservationLine.objects.get().consumed == 2
    assert InventoryMovement.objects.filter(kind='checked_return').count() == 1
    assert reconciliation(variant.pk)['matches']


def test_same_return_key_replays_under_contention(records):
    actor, (variant, _) = records
    previous = shipped(actor, variant)
    results = race([lambda: accept_return(actor, variant, previous, 'same-return'),
        lambda: accept_return(actor, variant, previous, 'same-return')])
    assert results[0] == results[1] and isinstance(results[0], ReservationResult)
    assert InventoryMovement.objects.filter(kind='checked_return').count() == 1
    assert InventoryChangeEvent.objects.count() == InventoryMovement.objects.count()


def test_duplicate_external_fact_allocates_and_commits_once(records):
    actor, (variant, _) = records
    fact = FakeSourceFact('same-source-fact', variant.pk, 'completed_sale', 2, 1)
    results = race([lambda: ingest_fake_fact(actor=actor, fact=fact, now=NOW),
        lambda: ingest_fake_fact(actor=actor, fact=fact, now=NOW)])
    assert results[0] == results[1] and results[0].status == 'applied'
    assert ExternalInventoryReceipt.objects.count() == ReservationLine.objects.count() == 1
    balance = StockBalance.objects.get(variant=variant)
    assert (balance.on_hand, balance.reserved) == (3, 2)
    assert InventoryMovement.objects.filter(source='fake_external').count() == 2
    assert reconciliation(variant.pk)['matches']


@pytest.mark.parametrize('kind', ['completed_sale', 'snapshot'])
def test_cross_variant_same_external_id_rolls_back_loser_and_keeps_conflict(records, kind):
    actor, variants = records
    barrier = Barrier(2)
    original_create = ExternalInventoryReceipt.objects.create

    def simultaneous_receipts(**kwargs):
        barrier.wait(timeout=10)
        return original_create(**kwargs)

    facts = [FakeSourceFact('global-external-id', variant.pk, kind, 2, 1,
        1 if kind == 'snapshot' else None) for variant in variants]
    with patch.object(ExternalInventoryReceipt.objects, 'create', side_effect=simultaneous_receipts):
        results = race([lambda: ingest_fake_fact(actor=actor, fact=facts[0], now=NOW),
            lambda: ingest_fake_fact(actor=actor, fact=facts[1], now=NOW)])
    assert sum(isinstance(result, IdempotencyConflictError) for result in results) == 1
    loser = next(i for i, result in enumerate(results) if isinstance(result, IdempotencyConflictError))
    balance = StockBalance.objects.get(variant=variants[loser])
    assert (balance.on_hand, balance.reserved, balance.revision) == (3, 0, 1)
    assert not ReservationLine.objects.filter(variant=variants[loser]).exists()
    assert ExternalInventoryReceipt.objects.count() == ExternalInventoryConflict.objects.count() == 1
    assert InventoryMovement.objects.count() == InventoryChangeEvent.objects.count() == (4 if kind == 'completed_sale' else 3)
    assert all(reconciliation(variant.pk)['matches'] for variant in variants)


def test_synthetic_sale_and_local_hold_share_last_unit_lock(records):
    actor, (variant, _) = records
    services.adjust(actor=actor, variant_id=variant.pk, quantity=1, context=ctx(actor, 'one-left', 1), now=NOW)
    fact = FakeSourceFact('competing-sale', variant.pk, 'completed_sale', 1, 1)
    results = race([lambda: ingest_fake_fact(actor=actor, fact=fact, now=NOW),
        lambda: services.reserve(actor=actor, variant_id=variant.pk, reservation_id='competing-local', quantity=1,
            context=ctx(actor, 'local-hold', 2), now=NOW, expires_at=NOW + timedelta(minutes=30))])
    assert results[0].status in ('applied', 'needs_attention')
    balance = StockBalance.objects.get(variant=variant)
    assert (balance.on_hand, balance.reserved, balance.on_hand - balance.reserved) == (1, 1, 0)
    assert ReservationLine.objects.filter(variant=variant).count() == 1
    assert reconciliation(variant.pk)['matches']


def test_committed_event_survives_no_enqueue_and_replay_visible_on_new_connection(records):
    actor, (variant, _) = records
    result = services.receive(actor=actor, variant_id=variant.pk, quantity=1, context=ctx(actor, 'before-crash', 1), now=NOW)
    # Service returned in autocommit. The process can stop before any enqueue.
    with pytest.raises(RuntimeError):
        raise RuntimeError('synthetic crash before enqueue')
    observed = race([lambda: InventoryChangeEvent.objects.filter(variant_id=variant.pk).count()])
    assert observed == [2]
    assert services.receive(actor=actor, variant_id=variant.pk, quantity=1,
        context=ctx(actor, 'before-crash', 1), now=NOW + timedelta(days=1)) == result
    observed = race([lambda: InventoryChangeEvent.objects.filter(variant_id=variant.pk).count()])
    assert observed == [2]


def test_due_hold_commits_after_fake_preflight_requires_retry_without_false_receipt(records):
    actor, (variant, _) = records
    scanned, held = Event(), Event()
    fact = FakeSourceFact('preflight-race', variant.pk, 'completed_sale', 1, 1)

    def pause_after_scan(**kwargs):
        opportunistic_cleanup(**kwargs)
        scanned.set()
        assert held.wait(timeout=10)

    def commit_due_hold():
        assert scanned.wait(timeout=10)
        result = services.reserve(actor=actor, variant_id=variant.pk, reservation_id='delayed-due', quantity=3,
            context=ctx(actor, 'delayed-hold', 1), now=NOW, expires_at=NOW + timedelta(seconds=1))
        held.set()
        return result

    with patch('web.inventory.fake_source_service.opportunistic_cleanup', side_effect=pause_after_scan):
        results = race([lambda: ingest_fake_fact(actor=actor, fact=fact, now=NOW + timedelta(seconds=1)), commit_due_hold])
    assert isinstance(results[0], ExpiryBacklogError)
    assert isinstance(results[1], ReservationResult)
    assert ExternalInventoryReceipt.objects.count() == 0
    result = ingest_fake_fact(actor=actor, fact=fact, now=NOW + timedelta(seconds=1))
    assert result.status == 'applied' and (result.stock.on_hand, result.stock.reserved) == (3, 1)
    assert InventoryMovement.objects.filter(kind='expire').count() == 1
    assert InventoryChangeEvent.objects.count() == InventoryMovement.objects.count()
    assert reconciliation(variant.pk)['matches']
