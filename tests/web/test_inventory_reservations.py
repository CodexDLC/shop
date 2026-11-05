from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, OperationalError, connection, transaction
from django.test.utils import CaptureQueriesContext

from codex_ecommerce.inventory import (
    IdempotencyConflictError,
    InsufficientStockError,
    InvalidQuantityError,
    InvalidTransitionError,
    InventoryInvariantError,
    OperationContext,
    ReservationExpiredError,
    ReservationState,
    StaleRevisionError,
)
from web.catalog.models import Brand, Category, Product, ProductVariant
from web.inventory import selectors, services
from web.inventory.models import InventoryMovement, ReservationLine
from web.inventory.write_access import service_write
from web.staff.models import StaffAuditEvent

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 11, 1, 12, tzinfo=UTC)
DEADLINE = NOW + timedelta(minutes=30)


@pytest.fixture
def records():
    actor = get_user_model().objects.create_user(username='reservation-owner', is_staff=True, is_superuser=True)
    brand = Brand.objects.create(slug='reservation-brand', name='Brand')
    category = Category.objects.create(slug='reservation-category', name_key='category')
    product = Product.objects.create(slug='reservation-product', model_name='Product', brand=brand, category=category)
    variant = ProductVariant.objects.create(product=product, sku='RESERVATION-1', color_code='black',
        color_name_key='black', size='M', price='10.00')
    services.initialize(actor=actor, variant_id=variant.pk, quantity=8, context=ctx(actor, 'init', 0))
    return actor, variant


def ctx(actor, key, revision):
    return OperationContext(key, 'staff', str(actor.pk), 'Isolated reservation QA', revision)


def reserve(actor, variant, reference='line-1', quantity=5, key='hold', revision=1, **kwargs):
    return services.reserve(actor=actor, variant_id=variant.pk, reservation_id=reference, quantity=quantity,
        context=ctx(actor, key, revision), expires_at=kwargs.pop('expires_at', DEADLINE),
        now=kwargs.pop('now', NOW), **kwargs)


def transition(command, actor, variant, previous, key, quantity=None, **kwargs):
    args = dict(actor=actor, variant_id=variant.pk, reservation_id=previous.reservation.reservation_id,
        context=ctx(actor, key, previous.stock.revision),
        expected_reservation_revision=previous.reservation.revision, now=NOW)
    if quantity is not None:
        args['quantity'] = quantity
    args.update(kwargs)
    return command(**args)


def test_reserve_commit_partial_fulfill_release_and_ledger_original_results(records):
    actor, variant = records
    held = reserve(actor, variant)
    committed = transition(services.commit, actor, variant, held, 'commit')
    fulfilled = transition(services.fulfill, actor, variant, committed, 'fulfill', quantity=2)
    closed = transition(services.release, actor, variant, fulfilled, 'release', quantity=3)
    assert (closed.stock.on_hand, closed.stock.reserved, closed.stock.revision) == (6, 0, 5)
    assert (closed.reservation.consumed, closed.reservation.released, closed.reservation.revision) == (2, 3, 4)
    assert closed.reservation.state is ReservationState.CLOSED
    assert reserve(actor, variant, now=DEADLINE + timedelta(days=1)) == held
    assert transition(services.commit, actor, variant, held, 'commit', now=DEADLINE + timedelta(days=1)) == committed
    assert selectors.reservation(actor=actor, reservation_id='line-1') == closed.reservation
    assert InventoryMovement.objects.count() == StaffAuditEvent.objects.count() == 5
    entry = InventoryMovement.objects.get(kind='fulfill')
    assert entry.reservation_id == 'line-1'
    assert entry.before_reservation['remaining_reserved'] == 5
    assert entry.after_reservation['remaining_reserved'] == 3
    assert (entry.delta_on_hand, entry.delta_reserved) == (-2, -2)
    assert selectors.stock(actor=actor, variant_id=variant.pk) == closed.stock


@pytest.mark.django_db(transaction=True)
def test_utc_deadline_normalization_and_expiry_boundary(records):
    actor, variant = records
    held = reserve(actor, variant, expires_at=DEADLINE.astimezone(timezone(timedelta(hours=2))))
    assert held.reservation.expires_at == DEADLINE
    assert reserve(actor, variant) == held
    with pytest.raises(ReservationExpiredError):
        transition(services.commit, actor, variant, held, 'late', now=DEADLINE)
    # S4 opportunistic expiry commits before late confirmation fails. Explicit
    # cancellation of an untouched expired HELD is covered in expiry tests.
    expired = selectors.reservation(actor=actor, reservation_id=held.reservation.reservation_id)
    assert expired.state is ReservationState.CLOSED and expired.released == 5
    assert selectors.stock(actor=actor, variant_id=variant.pk).reserved == 0
    assert InventoryMovement.objects.filter(kind='expire').count() == 1


@pytest.mark.parametrize('change', ['quantity', 'reference', 'deadline', 'balance_revision', 'reason', 'kind'])
def test_shared_dedup_payload_fingerprint(records, change):
    actor, variant = records
    reserve(actor, variant)
    args = dict(actor=actor, variant_id=variant.pk, reservation_id='line-1', quantity=5,
        context=ctx(actor, 'hold', 1), expires_at=DEADLINE, now=NOW)
    if change == 'quantity':
        args['quantity'] = 4
    elif change == 'reference':
        args['reservation_id'] = 'line-2'
    elif change == 'deadline':
        args['expires_at'] = DEADLINE + timedelta(seconds=1)
    elif change == 'balance_revision':
        args['context'] = replace(args['context'], expected_revision=2)
    elif change == 'reason':
        args['context'] = replace(args['context'], reason='Other reason')
    else:
        with pytest.raises(IdempotencyConflictError):
            services.receive(actor=actor, variant_id=variant.pk, quantity=5, context=ctx(actor, 'hold', 1))
        return
    with pytest.raises(IdempotencyConflictError):
        services.reserve(**args)


def test_accounting_key_and_reservation_revision_are_in_shared_payload(records):
    actor, variant = records
    with pytest.raises(IdempotencyConflictError):
        reserve(actor, variant, key='init', revision=0)
    held = reserve(actor, variant)
    committed = transition(services.commit, actor, variant, held, 'commit')
    with pytest.raises(IdempotencyConflictError):
        transition(services.commit, actor, variant, held, 'commit', expected_reservation_revision=0)
    with pytest.raises(StaleRevisionError):
        transition(services.release, actor, variant, held, 'stale', quantity=1)
    with pytest.raises(StaleRevisionError):
        transition(services.release, actor, variant, committed, 'stale-res', quantity=1, expected_reservation_revision=1)


def test_reference_not_reusable_after_close_and_oversell_rejected(records):
    actor, variant = records
    held = reserve(actor, variant)
    with pytest.raises(InsufficientStockError):
        reserve(actor, variant, reference='line-2', quantity=4, key='oversell', revision=2)
    closed = transition(services.release, actor, variant, held, 'release', quantity=5)
    with pytest.raises(InvalidTransitionError):
        reserve(actor, variant, key='new-attempt', revision=closed.stock.revision)
    assert ReservationLine.objects.count() == 1


def test_reference_global_uniqueness_and_identity_even_in_service_write_scope(records):
    actor, variant = records
    result = reserve(actor, variant)
    second = ProductVariant.objects.create(product=variant.product, sku='RESERVATION-2', color_code='black',
        color_name_key='black', size='L', price='10.00')
    services.initialize(actor=actor, variant_id=second.pk, quantity=8, context=ctx(actor, 'init-second', 0))
    with pytest.raises(InvalidTransitionError):
        reserve(actor, second, key='other-target')
    assert selectors.stock(actor=actor, variant_id=second.pk).reserved == 0
    for field, value in (('reference', 'another-ref'), ('variant_id', second.pk), ('location_id', 'other'), ('original', 99)):
        line = ReservationLine.objects.get()
        setattr(line, field, value)
        with service_write(), pytest.raises(PermissionDenied):
            line.save()
    with pytest.raises(IntegrityError):
        with transaction.atomic(), service_write():
            ReservationLine(reference='line-1', variant=second, original=3, remaining_reserved=3,
                consumed=0, released=0, state='held', expires_at=DEADLINE, revision=1).save()
    assert selectors.reservation(actor=actor, reservation_id='line-1') == result.reservation


def test_inactive_variant_blocks_new_holds_but_existing_obligations_can_finish(records):
    actor, variant = records
    held = reserve(actor, variant)
    variant.is_active = False
    variant.save()
    with pytest.raises(InventoryInvariantError):
        reserve(actor, variant, reference='line-2', quantity=1, key='new', revision=2)
    committed = transition(services.commit, actor, variant, held, 'commit')
    fulfilled = transition(services.fulfill, actor, variant, committed, 'fulfill', quantity=2)
    assert transition(services.release, actor, variant, fulfilled, 'release', quantity=3).stock.reserved == 0


@pytest.mark.parametrize('target', ['ledger', 'audit'])
@pytest.mark.parametrize('operation', ['reserve', 'commit', 'release', 'fulfill'])
def test_every_mutation_rolls_back_all_effects_on_persistence_failure(records, operation, target):
    actor, variant = records
    previous = None
    if operation != 'reserve':
        previous = reserve(actor, variant)
    if operation == 'fulfill':
        previous = transition(services.commit, actor, variant, previous, 'commit')
    before = selectors.stock(actor=actor, variant_id=variant.pk)
    count = InventoryMovement.objects.count()
    model = 'InventoryMovement' if target == 'ledger' else 'StaffAuditEvent'
    with patch(f'web.inventory.reservation_persistence.{model}.objects.create', side_effect=RuntimeError('injected')):
        with pytest.raises(RuntimeError):
            if operation == 'reserve':
                reserve(actor, variant)
            else:
                transition(getattr(services, operation), actor, variant, previous, 'mutate',
                    quantity=None if operation == 'commit' else 1)
    assert selectors.stock(actor=actor, variant_id=variant.pk) == before
    assert InventoryMovement.objects.count() == StaffAuditEvent.objects.count() == count
    assert ReservationLine.objects.count() == (0 if operation == 'reserve' else 1)
    if previous is not None:
        assert selectors.reservation(actor=actor, reservation_id='line-1') == previous.reservation


def test_native_action_rights_read_guards_and_forged_context(records):
    actor, variant = records
    held = reserve(actor, variant)
    with pytest.raises(PermissionDenied):
        services.reserve(actor=actor, variant_id=variant.pk, reservation_id='forged', quantity=1,
            context=replace(ctx(actor, 'forged', 2), source='ebay'), expires_at=DEADLINE, now=NOW)
    actor.is_superuser = False
    actor.save()
    with pytest.raises(PermissionDenied):
        reserve(actor, variant)
    with pytest.raises(PermissionDenied):
        selectors.reservations(actor=actor)
    actor.user_permissions.add(Permission.objects.get(content_type__app_label='inventory', codename='commit_reservationline'))
    committed = transition(services.commit, actor, variant, held, 'commit')
    for command in (services.release, services.fulfill):
        with pytest.raises(PermissionDenied):
            transition(command, actor, variant, committed, 'blocked', quantity=1)
    actor.user_permissions.clear()
    with pytest.raises(PermissionDenied):
        transition(services.commit, actor, variant, held, 'commit')
    actor.user_permissions.add(Permission.objects.get(content_type__app_label='inventory', codename='view_reservationline'))
    assert selectors.reservation(actor=actor, reservation_id='line-1') == committed.reservation
    actor.is_active = False
    actor.save()
    with pytest.raises(PermissionDenied):
        selectors.reservations(actor=actor)


def test_reservation_orm_guard_identity_and_constraints(records):
    actor, variant = records
    reserve(actor, variant)
    line = ReservationLine.objects.get()
    for mutation in (lambda: line.save(), lambda: line.delete(),
            lambda: ReservationLine.objects.update(original=99),
            lambda: ReservationLine.objects.all().delete(),
            lambda: ReservationLine.objects.bulk_update([line], ['remaining_reserved']),
            lambda: ReservationLine.objects.bulk_create([line])):
        with pytest.raises(PermissionDenied):
            mutation()
    assert ReservationLine not in admin.site._registry
    for assignment in ('remaining_reserved = 4', "state = 'unknown'", 'expires_at = NULL', 'revision = 0'):
        with pytest.raises(IntegrityError):
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(f'UPDATE inventory_reservationline SET {assignment}')


def test_reservation_reads_bounded_no_hidden_writes_and_no_n_plus_one(records):
    actor, variant = records
    for index in range(3):
        reserve(actor, variant, reference=f'line-{index}', quantity=1, key=f'hold-{index}', revision=index + 1)
    for limit in (1, 3):
        with CaptureQueriesContext(connection) as queries:
            lines = selectors.reservations(actor=actor, limit=limit)
            assert len(lines) == limit and all(line.variant.sku == variant.sku for line in lines)
        assert len(queries) == 2
    for limit in (0, 101, True):
        with pytest.raises(InventoryInvariantError):
            selectors.reservations(actor=actor, limit=limit)
    assert InventoryMovement.objects.count() == 4


@pytest.mark.parametrize('reference', ['address@example.test', 'https://example.test', ' ', 'x' * 101])
def test_opaque_reference_validation(records, reference):
    actor, variant = records
    with pytest.raises(InventoryInvariantError):
        reserve(actor, variant, reference=reference)


@pytest.mark.parametrize('revision', [True, 1.0, -1, 9223372036854775807])
def test_reservation_version_storage_bounds(records, revision):
    actor, variant = records
    held = reserve(actor, variant)
    with pytest.raises((InvalidQuantityError, InventoryInvariantError)):
        transition(services.commit, actor, variant, held, 'bad', expected_reservation_revision=revision)


def test_corrupt_stored_result_fails_closed_without_current_state_fallback(records):
    actor, variant = records
    held = reserve(actor, variant)
    transition(services.release, actor, variant, held, 'release', quantity=5)
    with connection.cursor() as cursor:
        cursor.execute("UPDATE inventory_inventorymovement SET after_reservation = '{}' WHERE kind = 'reserve'")
    with pytest.raises(InventoryInvariantError):
        reserve(actor, variant)


@pytest.mark.parametrize('bad_now', [NOW.replace(tzinfo=None), None, 'now'])
def test_now_validation_applies_before_replay(records, bad_now):
    actor, variant = records
    reserve(actor, variant)
    with pytest.raises(InventoryInvariantError):
        reserve(actor, variant, now=bad_now)


def test_unknown_target_location_or_reference_and_quantity_do_not_mutate(records):
    actor, variant = records
    for kwargs in ({'variant_id': 999999}, {'variant_id': True}, {'location_id': 'other'}):
        args = dict(actor=actor, variant_id=variant.pk, reservation_id='bad-target', quantity=1,
            context=ctx(actor, 'bad-target', 1), expires_at=DEADLINE, now=NOW)
        args.update(kwargs)
        with pytest.raises(InventoryInvariantError):
            services.reserve(**args)
    with pytest.raises(InventoryInvariantError):
        services.release(actor=actor, variant_id=variant.pk, reservation_id='unknown', quantity=1,
            context=ctx(actor, 'unknown', 1), expected_reservation_revision=1, now=NOW)
    with pytest.raises(InvalidQuantityError):
        reserve(actor, variant, quantity=0)
    assert not ReservationLine.objects.exists()
    assert InventoryMovement.objects.count() == StaffAuditEvent.objects.count() == 1


@pytest.mark.parametrize('operation', ['reserve', 'commit', 'release', 'fulfill'])
def test_each_action_accepts_only_its_native_permission(records, operation):
    actor, variant = records
    previous = None
    if operation != 'reserve':
        previous = reserve(actor, variant)
    if operation == 'fulfill':
        previous = transition(services.commit, actor, variant, previous, 'commit')
    actor.is_superuser = False
    actor.save()
    actor.user_permissions.add(Permission.objects.get(content_type__app_label='inventory',
        codename=f'{operation}_reservationline'))
    if operation == 'reserve':
        result = reserve(actor, variant)
    else:
        result = transition(getattr(services, operation), actor, variant, previous, 'allowed',
            quantity=None if operation == 'commit' else 1)
    assert result.reservation.revision >= 1
    with pytest.raises(PermissionDenied):
        selectors.reservation(actor=actor, reservation_id=result.reservation.reservation_id)


@pytest.mark.parametrize('code,recover,attempt_count', [
    ('40001', True, 2), ('40P01', True, 2), ('40001', False, 2), ('08006', False, 1),
])
def test_reservation_database_retry_is_atomic_specific_and_bounded(records, code, recover, attempt_count):
    actor, variant = records
    real_create = InventoryMovement.objects.create
    attempts = []

    def create_movement(**kwargs):
        attempts.append(kwargs)
        if recover and len(attempts) > 1:
            return real_create(**kwargs)
        cause = RuntimeError('injected database failure')
        cause.sqlstate = code
        error = OperationalError('injected database failure')
        error.__cause__ = cause
        raise error

    with patch('web.inventory.reservation_services.InventoryMovement.objects.create', side_effect=create_movement):
        if recover:
            assert reserve(actor, variant).stock.reserved == 5
        else:
            with pytest.raises(OperationalError):
                reserve(actor, variant)
    assert len(attempts) == attempt_count
    assert ReservationLine.objects.count() == int(recover)
    assert selectors.stock(actor=actor, variant_id=variant.pk).reserved == (5 if recover else 0)
    assert InventoryMovement.objects.count() == StaffAuditEvent.objects.count() == 1 + int(recover)


def test_unrelated_integrity_failure_does_not_become_reference_conflict_or_success(records):
    actor, variant = records
    with patch('web.inventory.reservation_services.InventoryMovement.objects.create', side_effect=IntegrityError('unrelated')):
        with pytest.raises(IntegrityError, match='unrelated'):
            reserve(actor, variant)
    assert not ReservationLine.objects.exists()
    assert selectors.stock(actor=actor, variant_id=variant.pk).reserved == 0
    assert reserve(actor, variant).stock.reserved == 5
