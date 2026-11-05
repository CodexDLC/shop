from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.db.models import Sum

from codex_ecommerce.inventory import (
    IdempotencyConflictError,
    InsufficientStockError,
    InvalidQuantityError,
    InvalidTransitionError,
    OperationContext,
    ReservationResult,
    StaleRevisionError,
)
from web.catalog.models import Brand, Category, Product, ProductVariant
from web.inventory import reservation_services, selectors, services
from web.inventory.models import InventoryMovement, ReservationLine, StockBalance
from web.staff.models import StaffAuditEvent

pytestmark = [pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != 'postgresql', reason='Requires isolated PostgreSQL test database')]
NOW = datetime(2026, 11, 1, 12, tzinfo=UTC)
DEADLINE = NOW + timedelta(minutes=30)


@pytest.fixture
def records():
    actor = get_user_model().objects.create_user(username='reservation-concurrent', is_staff=True, is_superuser=True)
    brand = Brand.objects.create(slug='reservation-concurrent', name='Brand')
    category = Category.objects.create(slug='reservation-concurrent', name_key='category')
    product = Product.objects.create(slug='reservation-concurrent', model_name='Product', brand=brand, category=category)
    variants = [ProductVariant.objects.create(product=product, sku=f'RESERVATION-CONCURRENT-{index}',
        color_code='black', color_name_key='black', size=str(index), price='10.00') for index in range(2)]
    return actor, variants


def ctx(actor, key, revision):
    return OperationContext(key, 'staff', str(actor.pk), 'Isolated reservation concurrency QA', revision)


def initialize(actor, variant, quantity):
    return services.initialize(actor=actor, variant_id=variant.pk, quantity=quantity,
        context=ctx(actor, f'init-{variant.pk}', 0))


def reserve(actor, variant, reference, quantity=1, key=None, revision=1, now=NOW):
    return services.reserve(actor=actor, variant_id=variant.pk, reservation_id=reference, quantity=quantity,
        context=ctx(actor, key or f'hold-{reference}', revision), expires_at=DEADLINE, now=now)


def transition(command, actor, variant, previous, key, quantity=None):
    args = dict(actor=actor, variant_id=variant.pk, reservation_id=previous.reservation.reservation_id,
        context=ctx(actor, key, previous.stock.revision), expected_reservation_revision=previous.reservation.revision,
        now=NOW)
    if quantity is not None:
        args['quantity'] = quantity
    return command(**args)


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
            except (StaleRevisionError, InvalidTransitionError, IdempotencyConflictError) as error:
                return backend, error
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=len(functions)) as executor:
        futures = [executor.submit(run, function) for function in functions]
        results = [future.result(timeout=20) for future in futures]
    assert len({backend for backend, _ in results}) == len(functions)
    return [value for _, value in results]


def assert_conserved(variant):
    balance = StockBalance.objects.get(variant=variant)
    totals = ReservationLine.objects.filter(variant=variant).aggregate(remaining=Sum('remaining_reserved'))
    assert balance.reserved == (totals['remaining'] or 0)
    assert 0 <= balance.reserved <= balance.on_hand
    for line in ReservationLine.objects.filter(variant=variant):
        assert line.original == line.remaining_reserved + line.consumed + line.released


def test_last_unit_race_stale_then_insufficient_with_no_oversell(records):
    actor, (variant, _) = records
    initialize(actor, variant, 1)
    results = race([lambda: reserve(actor, variant, 'last-a'), lambda: reserve(actor, variant, 'last-b')])
    assert sum(isinstance(result, StaleRevisionError) for result in results) == 1
    loser = next(index for index, result in enumerate(results) if isinstance(result, StaleRevisionError))
    current = selectors.stock(actor=actor, variant_id=variant.pk)
    with pytest.raises(InsufficientStockError):
        reserve(actor, variant, ('last-a', 'last-b')[loser], revision=current.revision)
    assert ReservationLine.objects.count() == 1
    assert InventoryMovement.objects.count() == StaffAuditEvent.objects.count() == 2
    assert_conserved(variant)


def test_same_key_concurrent_hold_and_commit_replay_original_result(records):
    actor, (variant, _) = records
    initialize(actor, variant, 3)
    results = race([lambda: reserve(actor, variant, 'same-ref', key='same-key'),
        lambda: reserve(actor, variant, 'same-ref', key='same-key', now=NOW + timedelta(seconds=1))])
    assert results[0] == results[1] and isinstance(results[0], ReservationResult)
    held = results[0]
    commits = race([lambda: transition(services.commit, actor, variant, held, 'commit'),
        lambda: transition(services.commit, actor, variant, held, 'commit')])
    assert commits[0] == commits[1]
    transition(services.release, actor, variant, commits[0], 'cancel', quantity=1)
    assert reserve(actor, variant, 'same-ref', key='same-key', now=DEADLINE + timedelta(days=1)) == held
    assert transition(services.commit, actor, variant, held, 'commit') == commits[0]
    assert InventoryMovement.objects.count() == StaffAuditEvent.objects.count() == 4
    assert_conserved(variant)


def test_competing_release_fulfill_versions_prevent_double_consumption(records):
    actor, (variant, _) = records
    initialize(actor, variant, 3)
    held = reserve(actor, variant, 'competing', quantity=3)
    committed = transition(services.commit, actor, variant, held, 'commit')
    methods = (services.release, services.fulfill)
    results = race([lambda: transition(methods[0], actor, variant, committed, 'release', quantity=2),
        lambda: transition(methods[1], actor, variant, committed, 'fulfill', quantity=2)])
    assert sum(isinstance(result, StaleRevisionError) for result in results) == 1
    winner = next(result for result in results if isinstance(result, ReservationResult))
    loser_index = next(index for index, result in enumerate(results) if isinstance(result, StaleRevisionError))
    with pytest.raises(InvalidQuantityError):
        transition(methods[loser_index], actor, variant, winner, 'over-remaining', quantity=2)
    assert InventoryMovement.objects.count() == StaffAuditEvent.objects.count() == 4
    assert selectors.stock(actor=actor, variant_id=variant.pk).reserved == 1
    line = ReservationLine.objects.get()
    balance = StockBalance.objects.get()
    assert balance.on_hand + line.consumed == 3
    assert_conserved(variant)


def test_accounting_and_reserve_share_balance_lock_and_revisions(records):
    actor, (variant, _) = records
    initialize(actor, variant, 1)
    results = race([lambda: services.receive(actor=actor, variant_id=variant.pk, quantity=1,
        context=ctx(actor, 'receive', 1), now=NOW), lambda: reserve(actor, variant, 'hold')])
    assert sum(isinstance(result, StaleRevisionError) for result in results) == 1
    current = selectors.stock(actor=actor, variant_id=variant.pk)
    if isinstance(results[0], StaleRevisionError):
        services.receive(actor=actor, variant_id=variant.pk, quantity=1,
            context=ctx(actor, 'receive', current.revision), now=NOW)
    else:
        reserve(actor, variant, 'hold', revision=current.revision)
    current = selectors.stock(actor=actor, variant_id=variant.pk)
    assert (current.on_hand, current.reserved, current.revision) == (2, 1, 3)
    assert_conserved(variant)


def test_cross_target_scoped_key_collision_rolls_back_balance_and_reservation(records):
    actor, variants = records
    for variant in variants:
        initialize(actor, variant, 3)
    barrier = Barrier(2)
    calculate = reservation_services.reserve_stock

    def synchronized_calculate(*args, **kwargs):
        result = calculate(*args, **kwargs)
        barrier.wait(timeout=10)
        return result

    with patch('web.inventory.reservation_services.reserve_stock', side_effect=synchronized_calculate):
        results = race([lambda: reserve(actor, variants[0], 'target-a', key='cross-target'),
            lambda: reserve(actor, variants[1], 'target-b', key='cross-target')])
    assert sum(isinstance(result, IdempotencyConflictError) for result in results) == 1
    loser = next(index for index, result in enumerate(results) if isinstance(result, IdempotencyConflictError))
    assert selectors.stock(actor=actor, variant_id=variants[loser].pk).reserved == 0
    assert not ReservationLine.objects.filter(variant=variants[loser]).exists()
    assert InventoryMovement.objects.count() == StaffAuditEvent.objects.count() == 3
    for variant in variants:
        assert_conserved(variant)


def test_global_reference_creation_race_different_targets_has_one_owner(records):
    actor, variants = records
    for variant in variants:
        initialize(actor, variant, 3)
    barrier = Barrier(2)
    calculate = reservation_services.reserve_stock

    def synchronized_calculate(*args, **kwargs):
        result = calculate(*args, **kwargs)
        barrier.wait(timeout=10)
        return result

    with patch('web.inventory.reservation_services.reserve_stock', side_effect=synchronized_calculate):
        results = race([lambda: reserve(actor, variants[0], 'unique-ref', key='owner-a'),
            lambda: reserve(actor, variants[1], 'unique-ref', key='owner-b')])
    assert sum(isinstance(result, InvalidTransitionError) for result in results) == 1
    assert ReservationLine.objects.count() == 1
    assert InventoryMovement.objects.count() == StaffAuditEvent.objects.count() == 3
    for variant in variants:
        assert_conserved(variant)


def test_multi_line_partial_operations_preserve_global_reserved_sum(records):
    actor, (variant, _) = records
    initialize(actor, variant, 6)
    first = reserve(actor, variant, 'first', quantity=4)
    second = reserve(actor, variant, 'second', quantity=2, revision=first.stock.revision)
    first = services.commit(actor=actor, variant_id=variant.pk, reservation_id='first',
        context=ctx(actor, 'commit-first', second.stock.revision), expected_reservation_revision=1, now=NOW)
    assert_conserved(variant)
    first = transition(services.fulfill, actor, variant, first, 'fulfill-first', quantity=3)
    assert_conserved(variant)
    first = transition(services.release, actor, variant, first, 'release-first', quantity=1)
    assert_conserved(variant)
    services.release(actor=actor, variant_id=variant.pk, reservation_id='second', quantity=2,
        context=ctx(actor, 'release-second', first.stock.revision), expected_reservation_revision=1, now=NOW)
    assert_conserved(variant)
    assert selectors.stock(actor=actor, variant_id=variant.pk).reserved == 0
