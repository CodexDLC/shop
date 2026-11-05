from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, Event
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.db.models import Sum

from codex_ecommerce.inventory import OperationContext, ReservationExpiredError, StaleRevisionError
from web.catalog.models import Brand, Category, Product, ProductVariant
from web.inventory import expiry_service, reservation_services, selectors, services
from web.inventory.expiry_backlog_error import ExpiryBacklogError
from web.inventory.expiry_service import expire_due_reservations
from web.inventory.models import InventoryMovement, ReservationLine, StockBalance
from web.staff.models import StaffAuditEvent

pytestmark = [pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != 'postgresql', reason='Requires isolated PostgreSQL test database')]
NOW = datetime(2026, 11, 1, 12, tzinfo=UTC)
DEADLINE = NOW + timedelta(minutes=30)


def ctx(actor, key, revision):
    return OperationContext(key, 'staff', str(actor.pk), 'Isolated expiry concurrency QA', revision)


@pytest.fixture
def records():
    actor = get_user_model().objects.create_user(username='expiry-concurrent', is_staff=True, is_superuser=True)
    brand = Brand.objects.create(slug='expiry-concurrent', name='Brand')
    category = Category.objects.create(slug='expiry-concurrent', name_key='category')
    product = Product.objects.create(slug='expiry-concurrent', model_name='Product', brand=brand, category=category)
    variant = ProductVariant.objects.create(product=product, sku='EXPIRY-CONCURRENT', color_code='black',
        color_name_key='black', size='M', price='10.00')
    services.initialize(actor=actor, variant_id=variant.pk, quantity=8, context=ctx(actor, 'init', 0), now=NOW)
    return actor, variant


def hold(actor, variant, reference='line', quantity=5):
    stock = selectors.stock(actor=actor, variant_id=variant.pk)
    return services.reserve(actor=actor, variant_id=variant.pk, reservation_id=reference, quantity=quantity,
        context=ctx(actor, f'hold-{reference}', stock.revision), expires_at=DEADLINE, now=NOW)


def commit(actor, variant, previous, now=NOW):
    return services.commit(actor=actor, variant_id=variant.pk, reservation_id='line',
        context=ctx(actor, 'commit', previous.stock.revision), expected_reservation_revision=previous.reservation.revision,
        now=now)


def threaded(function):
    close_old_connections()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET lock_timeout = '5s'")
            cursor.execute("SET statement_timeout = '10s'")
            cursor.execute('SELECT pg_backend_pid()')
            backend = cursor.fetchone()[0]
        try:
            return backend, function()
        except (StaleRevisionError, ReservationExpiredError, ExpiryBacklogError) as error:
            return backend, error
    finally:
        connection.close()


def race(functions):
    start = Barrier(len(functions))

    def run(function):
        return threaded(lambda: (start.wait(timeout=10), function())[1])

    with ThreadPoolExecutor(max_workers=len(functions)) as executor:
        futures = [executor.submit(run, function) for function in functions]
        values = [future.result(timeout=20) for future in futures]
    assert len({backend for backend, _ in values}) == len(functions)
    return [value for _, value in values]


def assert_conserved(variant):
    stock = StockBalance.objects.get(variant=variant)
    totals = ReservationLine.objects.filter(variant=variant).aggregate(remaining=Sum('remaining_reserved'))
    assert stock.reserved == (totals['remaining'] or 0)
    assert 0 <= stock.reserved <= stock.on_hand
    for line in ReservationLine.objects.filter(variant=variant):
        assert line.original == line.remaining_reserved + line.consumed + line.released


def test_two_cleanup_calls_expire_each_line_exactly_once(records):
    actor, variant = records
    hold(actor, variant)
    selected = Barrier(2)
    expire_one = expiry_service._expire_one

    def synchronized_expire(**kwargs):
        selected.wait(timeout=10)
        return expire_one(**kwargs)

    with patch('web.inventory.expiry_service._expire_one', side_effect=synchronized_expire):
        summaries = race([lambda: expire_due_reservations(actor=actor, now=DEADLINE),
            lambda: expire_due_reservations(actor=actor, now=DEADLINE)])
    assert sum(summary.expired for summary in summaries) == 1
    assert InventoryMovement.objects.filter(kind='expire').count() == 1
    assert InventoryMovement.objects.count() == StaffAuditEvent.objects.count() == 3
    assert_conserved(variant)


def test_commit_and_expiry_race_yields_only_committed_or_expired(records):
    actor, variant = records
    original = hold(actor, variant)
    results = race([lambda: commit(actor, variant, original),
        lambda: expire_due_reservations(actor=actor, now=DEADLINE)])
    line = ReservationLine.objects.get()
    if line.state == 'committed':
        assert line.remaining_reserved == 5 and line.released == 0
        assert InventoryMovement.objects.filter(kind='commit').count() == 1
        assert not InventoryMovement.objects.filter(kind='expire').exists()
        assert commit(actor, variant, original, now=DEADLINE + timedelta(days=1)) == results[0]
    else:
        assert line.state == 'closed' and line.released == 5
        assert InventoryMovement.objects.filter(kind='expire').count() == 1
        assert not InventoryMovement.objects.filter(kind='commit').exists()
        assert isinstance(results[0], ReservationExpiredError)
    assert_conserved(variant)


def test_cancel_and_expiry_race_release_only_once(records):
    actor, variant = records
    original = hold(actor, variant)

    def cancel():
        return services.release(actor=actor, variant_id=variant.pk, reservation_id='line', quantity=5,
            context=ctx(actor, 'cancel', original.stock.revision), expected_reservation_revision=1, now=DEADLINE)

    race([cancel, lambda: expire_due_reservations(actor=actor, now=DEADLINE)])
    line = ReservationLine.objects.get()
    assert line.state == 'closed' and line.released == 5 and line.consumed == 0
    assert InventoryMovement.objects.filter(kind__in=['release', 'expire']).count() == 1
    assert_conserved(variant)


def test_cleanup_nowait_skips_in_flight_commit_then_preserves_partial_shipment(records):
    actor, variant = records
    original = hold(actor, variant)
    locked, resume = Event(), Event()
    calculate = reservation_services.commit_reservation

    def paused_calculation(*args, **kwargs):
        locked.set()
        assert resume.wait(timeout=10)
        return calculate(*args, **kwargs)

    with patch('web.inventory.reservation_services.commit_reservation', side_effect=paused_calculation):
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(threaded, lambda: commit(actor, variant, original))
            try:
                assert locked.wait(timeout=10)
                summary = expire_due_reservations(actor=actor, now=DEADLINE)
                assert (summary.scanned, summary.expired, summary.skipped, summary.has_more) == (1, 0, 1, True)
            finally:
                resume.set()
            _, committed = future.result(timeout=15)
    partial = services.fulfill(actor=actor, variant_id=variant.pk, reservation_id='line', quantity=2,
        context=ctx(actor, 'ship', committed.stock.revision), expected_reservation_revision=2,
        now=DEADLINE + timedelta(minutes=1))
    assert expire_due_reservations(actor=actor, now=DEADLINE + timedelta(days=1)).expired == 0
    assert selectors.reservation(actor=actor, reservation_id='line') == partial.reservation
    assert not InventoryMovement.objects.filter(kind='expire').exists()
    assert_conserved(variant)


def test_stopped_worker_opportunistic_expiry_commits_despite_main_failure(records):
    actor, variant = records
    original = hold(actor, variant)
    with pytest.raises(StaleRevisionError):
        services.receive(actor=actor, variant_id=variant.pk, quantity=1,
            context=ctx(actor, 'receipt', original.stock.revision), now=DEADLINE)
    assert InventoryMovement.objects.filter(kind='expire').count() == 1
    assert not InventoryMovement.objects.filter(operation_key='receipt').exists()
    stock = selectors.stock(actor=actor, variant_id=variant.pk)
    assert (stock.on_hand, stock.reserved) == (8, 0)
    services.receive(actor=actor, variant_id=variant.pk, quantity=1,
        context=ctx(actor, 'receipt', stock.revision), now=DEADLINE)
    assert_conserved(variant)


def test_batch_failure_keeps_prior_commits_and_retry_continues(records):
    actor, variant = records
    for index in range(3):
        hold(actor, variant, reference=f'line-{index}', quantity=1)
    actual_create = StaffAuditEvent.objects.create
    attempts = []

    def audit(**kwargs):
        attempts.append(kwargs)
        if len(attempts) == 2:
            raise RuntimeError('injected failure')
        return actual_create(**kwargs)

    with patch('web.inventory.expiry_service.StaffAuditEvent.objects.create', side_effect=audit):
        with pytest.raises(RuntimeError, match='injected failure'):
            expire_due_reservations(actor=actor, now=DEADLINE)
    assert InventoryMovement.objects.filter(kind='expire').count() == 1
    assert expire_due_reservations(actor=actor, now=DEADLINE).expired == 2
    assert InventoryMovement.objects.filter(kind='expire').count() == 3
    assert_conserved(variant)
