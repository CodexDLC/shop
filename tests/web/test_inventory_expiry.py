from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, OperationalError, transaction

from codex_ecommerce.inventory import (
    OperationContext,
    ReservationExpiredError,
    ReservationState,
    StaleRevisionError,
)
from web.catalog.models import Brand, Category, Product, ProductVariant
from web.inventory import selectors, services
from web.inventory.expiry_backlog_error import ExpiryBacklogError
from web.inventory.expiry_service import due_reservations, expire_due_reservations
from web.inventory.expiry_transaction_error import ExpiryTransactionError
from web.inventory.models import InventoryMovement, ReservationLine
from web.staff.models import StaffAuditEvent

pytestmark = pytest.mark.django_db(transaction=True)
NOW = datetime(2026, 11, 1, 12, tzinfo=UTC)
DEADLINE = NOW + timedelta(minutes=30)


def ctx(actor, key, revision):
    return OperationContext(key, 'staff', str(actor.pk), 'Isolated expiry QA', revision)


@pytest.fixture
def records():
    actor = get_user_model().objects.create_user(username='expiry-owner', is_staff=True, is_superuser=True)
    brand = Brand.objects.create(slug='expiry-brand', name='Brand')
    category = Category.objects.create(slug='expiry-category', name_key='category')
    product = Product.objects.create(slug='expiry-product', model_name='Product', brand=brand, category=category)
    variant = ProductVariant.objects.create(product=product, sku='EXPIRY-1', color_code='black',
        color_name_key='black', size='M', price='10.00')
    services.initialize(actor=actor, variant_id=variant.pk, quantity=100, context=ctx(actor, 'init', 0), now=NOW)
    return actor, variant


def hold(actor, variant, reference='line', quantity=3):
    stock = selectors.stock(actor=actor, variant_id=variant.pk)
    return services.reserve(actor=actor, variant_id=variant.pk, reservation_id=reference, quantity=quantity,
        context=ctx(actor, f'hold-{reference}', stock.revision), expires_at=DEADLINE, now=NOW)


def commit(actor, variant, previous, key='commit', now=NOW):
    return services.commit(actor=actor, variant_id=variant.pk, reservation_id=previous.reservation.reservation_id,
        context=ctx(actor, key, previous.stock.revision), expected_reservation_revision=previous.reservation.revision, now=now)


def test_batch_boundary_canonical_ledger_and_idempotent_repeat(records):
    actor, variant = records
    original = hold(actor, variant)
    assert expire_due_reservations(actor=actor, now=DEADLINE - timedelta(microseconds=1)).expired == 0
    summary = expire_due_reservations(actor=actor, now=DEADLINE)
    assert (summary.scanned, summary.expired, summary.skipped, summary.has_more) == (1, 1, 0, False)
    with pytest.raises(FrozenInstanceError):
        summary.expired = 2
    line = selectors.reservation(actor=actor, reservation_id='line')
    stock = selectors.stock(actor=actor, variant_id=variant.pk)
    assert line.state is ReservationState.CLOSED and line.released == 3
    assert (stock.on_hand, stock.reserved, stock.revision) == (100, 0, 3)
    movement = InventoryMovement.objects.get(kind='expire')
    assert (movement.source, movement.owner, movement.operation_key) == ('inventory_expiry', 'system', 'expire:line')
    assert (movement.delta_on_hand, movement.delta_reserved) == (0, -3)
    assert movement.decision_at == DEADLINE
    assert expire_due_reservations(actor=actor, now=DEADLINE).scanned == 0
    assert InventoryMovement.objects.count() == StaffAuditEvent.objects.count() == 3
    assert services.reserve(actor=actor, variant_id=variant.pk, reservation_id='line', quantity=3,
        context=ctx(actor, 'hold-line', 1), expires_at=DEADLINE, now=DEADLINE) == original


def test_committed_and_partially_fulfilled_never_expire_successful_commit_replays(records):
    actor, variant = records
    original = hold(actor, variant)
    committed = commit(actor, variant, original)
    partial = services.fulfill(actor=actor, variant_id=variant.pk, reservation_id='line', quantity=1,
        context=ctx(actor, 'ship', committed.stock.revision), expected_reservation_revision=2, now=NOW)
    assert expire_due_reservations(actor=actor, now=DEADLINE + timedelta(days=1)).expired == 0
    assert selectors.reservation(actor=actor, reservation_id='line') == partial.reservation
    assert commit(actor, variant, original, now=DEADLINE + timedelta(days=1)) == committed


def test_failed_late_commit_preserves_independent_expiry_and_stable_review_error(records):
    actor, variant = records
    original = hold(actor, variant)
    for _ in range(2):
        with pytest.raises(ReservationExpiredError) as error:
            commit(actor, variant, original, key='late', now=DEADLINE)
        assert error.value.code == 'reservation_expired' and error.value.action == 'review_reservation'
    assert selectors.stock(actor=actor, variant_id=variant.pk).reserved == 0
    assert InventoryMovement.objects.filter(kind='expire').count() == 1
    assert not InventoryMovement.objects.filter(operation_key='late').exists()


@pytest.mark.parametrize('command', ['receive', 'adjust', 'reserve'])
def test_opportunistic_cleanup_survives_failed_cas_and_requires_explicit_refresh(records, command):
    actor, variant = records
    original = hold(actor, variant)
    if command == 'reserve':
        args = dict(reservation_id='new-line', expires_at=DEADLINE + timedelta(minutes=30))
    else:
        args = {}
    quantity = 1 if command != 'adjust' else 80
    with pytest.raises(StaleRevisionError):
        getattr(services, command)(actor=actor, variant_id=variant.pk, quantity=quantity,
            context=ctx(actor, 'main', original.stock.revision), now=DEADLINE, **args)
    stock = selectors.stock(actor=actor, variant_id=variant.pk)
    assert stock.reserved == 0 and stock.on_hand == 100
    assert InventoryMovement.objects.filter(kind='expire').count() == 1
    result = getattr(services, command)(actor=actor, variant_id=variant.pk, quantity=quantity,
        context=ctx(actor, 'main', stock.revision), now=DEADLINE, **args)
    assert (result.stock if command == 'reserve' else result).revision == 4


def test_explicit_cancel_of_own_expired_hold_is_release_and_no_expiry(records):
    actor, variant = records
    hold(actor, variant)
    result = services.release(actor=actor, variant_id=variant.pk, reservation_id='line', quantity=3,
        context=ctx(actor, 'cancel', 2), expected_reservation_revision=1, now=DEADLINE)
    assert result.stock.reserved == 0 and result.reservation.released == 3
    assert not InventoryMovement.objects.filter(kind='expire').exists()


def test_batch_bounded_partial_progress_retry_after_audit_failure(records):
    actor, variant = records
    for index in range(3):
        hold(actor, variant, reference=f'line-{index}', quantity=1)
    preview = due_reservations(actor=actor, now=DEADLINE, batch_size=2)
    assert preview.scanned == preview.skipped == 2 and preview.expired == 0 and preview.has_more
    create = StaffAuditEvent.objects.create
    attempts = []

    def audit(**kwargs):
        attempts.append(kwargs)
        if len(attempts) == 2:
            raise RuntimeError('injected')
        return create(**kwargs)

    with patch('web.inventory.expiry_service.StaffAuditEvent.objects.create', side_effect=audit):
        with pytest.raises(RuntimeError, match='injected'):
            expire_due_reservations(actor=actor, now=DEADLINE, batch_size=3)
    assert InventoryMovement.objects.filter(kind='expire').count() == 1
    summary = expire_due_reservations(actor=actor, now=DEADLINE, batch_size=1)
    assert summary.expired == 1 and summary.has_more
    assert expire_due_reservations(actor=actor, now=DEADLINE, batch_size=3).expired == 1
    assert selectors.stock(actor=actor, variant_id=variant.pk).reserved == 0


def test_due_selectors_do_not_write_and_outer_atomic_rejected_before_cleanup(records):
    actor, variant = records
    original = hold(actor, variant)
    assert selectors.stock(actor=actor, variant_id=variant.pk).reserved == 3
    with transaction.atomic():
        assert due_reservations(actor=actor, now=DEADLINE).scanned == 1
        with pytest.raises(ExpiryTransactionError):
            expire_due_reservations(actor=actor, now=DEADLINE)
        with pytest.raises(ExpiryTransactionError):
            commit(actor, variant, original, now=DEADLINE)
    assert selectors.stock(actor=actor, variant_id=variant.pk).reserved == 3
    assert not InventoryMovement.objects.filter(kind='expire').exists()


def test_unauthorized_calls_and_forged_expiry_scope_have_no_effects(records):
    actor, variant = records
    hold(actor, variant)
    actor.is_superuser = False
    actor.save()
    for function in (expire_due_reservations, due_reservations):
        with pytest.raises(PermissionDenied):
            function(actor=actor, now=DEADLINE)
    actor.user_permissions.add(Permission.objects.get(content_type__app_label='inventory', codename='receive_stockbalance'))
    with pytest.raises(PermissionDenied):
        services.receive(actor=actor, variant_id=variant.pk, quantity=1,
            context=OperationContext('expire:line', 'inventory_expiry', 'system', 'forged', 2), now=DEADLINE)
    assert ReservationLine.objects.get().state == 'held'
    actor.user_permissions.add(Permission.objects.get(content_type__app_label='inventory', codename='expire_reservationline'))
    assert expire_due_reservations(actor=actor, now=DEADLINE).expired == 1


def test_per_sku_backlog_is_bounded_and_main_command_not_applied(records):
    actor, variant = records
    for index in range(22):
        hold(actor, variant, reference=f'line-{index:02}', quantity=1)
    with pytest.raises(ExpiryBacklogError) as error:
        services.receive(actor=actor, variant_id=variant.pk, quantity=1, context=ctx(actor, 'main', 23), now=DEADLINE)
    assert error.value.code == 'expiry_backlog' and error.value.action == 'retry_cleanup'
    assert InventoryMovement.objects.filter(kind='expire').count() == 20
    assert not InventoryMovement.objects.filter(operation_key='main').exists()
    assert selectors.stock(actor=actor, variant_id=variant.pk).reserved == 2


@pytest.mark.parametrize('size', [0, 101, True, 1.5])
def test_batch_size_validation(records, size):
    actor, _ = records
    with pytest.raises(ValueError):
        expire_due_reservations(actor=actor, now=DEADLINE, batch_size=size)


def test_manual_command_defaults_dry_run_requires_explicit_apply_and_actor(records):
    actor, variant = records
    hold(actor, variant)
    output = StringIO()
    with patch('web.inventory.management.commands.expire_inventory_reservations.timezone.now', return_value=DEADLINE):
        call_command('expire_inventory_reservations', actor=actor.pk, stdout=output)
        assert 'dry_run=True' in output.getvalue() and 'scanned=1' in output.getvalue()
        assert not InventoryMovement.objects.filter(kind='expire').exists()
        call_command('expire_inventory_reservations', actor=actor.pk, apply=True, stdout=output)
    assert 'expired=1' in output.getvalue()
    actor.is_active = False
    actor.save()
    with pytest.raises(CommandError):
        call_command('expire_inventory_reservations', actor=actor.pk, apply=True)


@pytest.mark.parametrize('model', ['InventoryMovement', 'StaffAuditEvent'])
def test_per_line_failure_rolls_back_every_effect_and_does_not_claim_canonical_key(records, model):
    actor, variant = records
    original = hold(actor, variant)
    with patch(f'web.inventory.expiry_service.{model}.objects.create', side_effect=RuntimeError('injected')):
        with pytest.raises(RuntimeError, match='injected'):
            expire_due_reservations(actor=actor, now=DEADLINE)
    assert selectors.reservation(actor=actor, reservation_id='line') == original.reservation
    assert selectors.stock(actor=actor, variant_id=variant.pk) == original.stock
    assert not InventoryMovement.objects.filter(kind='expire').exists()
    assert expire_due_reservations(actor=actor, now=DEADLINE).expired == 1


def test_time_budget_stops_before_processing_and_leaves_actionable_has_more(records):
    actor, variant = records
    hold(actor, variant)
    with patch('web.inventory.expiry_service.monotonic', side_effect=[0.0, 6.0]):
        summary = expire_due_reservations(actor=actor, now=DEADLINE)
    assert (summary.scanned, summary.expired, summary.skipped, summary.has_more) == (0, 0, 0, True)
    assert selectors.stock(actor=actor, variant_id=variant.pk).reserved == 3


def test_locked_target_is_skipped_bounded_and_opportunistic_main_refuses_backlog(records):
    actor, variant = records
    original = hold(actor, variant)
    cause = RuntimeError('injected lock contention')
    cause.sqlstate = '55P03'
    error = OperationalError('injected lock contention')
    error.__cause__ = cause
    with patch('web.inventory.expiry_service.ProductVariant.objects.select_for_update', side_effect=error):
        summary = expire_due_reservations(actor=actor, now=DEADLINE)
        assert (summary.scanned, summary.expired, summary.skipped, summary.has_more) == (1, 0, 1, True)
        with pytest.raises(ExpiryBacklogError):
            services.receive(actor=actor, variant_id=variant.pk, quantity=1,
                context=ctx(actor, 'main', original.stock.revision), now=DEADLINE)
    assert selectors.stock(actor=actor, variant_id=variant.pk) == original.stock


def test_main_permission_authorizes_internal_maintenance_without_batch_permission(records):
    actor, variant = records
    hold(actor, variant)
    actor.is_superuser = False
    actor.save()
    actor.user_permissions.add(Permission.objects.get(content_type__app_label='inventory', codename='receive_stockbalance'))
    with pytest.raises(PermissionDenied):
        expire_due_reservations(actor=actor, now=DEADLINE)
    with pytest.raises(StaleRevisionError):
        services.receive(actor=actor, variant_id=variant.pk, quantity=1, context=ctx(actor, 'main', 2), now=DEADLINE)
    assert InventoryMovement.objects.filter(kind='expire', actor=actor).count() == 1


def test_successful_old_replay_leaves_unrelated_due_work_untouched(records):
    actor, variant = records
    first = hold(actor, variant, reference='first')
    hold(actor, variant, reference='second')
    replay = services.reserve(actor=actor, variant_id=variant.pk, reservation_id='first', quantity=3,
        context=ctx(actor, 'hold-first', 1), expires_at=DEADLINE, now=DEADLINE)
    assert replay == first
    assert ReservationLine.objects.filter(state='held').count() == 2
    assert not InventoryMovement.objects.filter(kind='expire').exists()


def test_manual_command_database_failure_is_sanitized_without_query_or_secret(records):
    actor, _ = records
    with patch('web.inventory.management.commands.expire_inventory_reservations.get_user_model',
            side_effect=DatabaseError('SELECT sensitive_private_details secret-token')):
        with pytest.raises(CommandError) as error:
            call_command('expire_inventory_reservations', actor=actor.pk, apply=True)
    assert str(error.value) == 'Inventory expiry database unavailable; check configuration and migrations.'
    assert error.value.__suppress_context__


@pytest.mark.parametrize('code,recover,attempt_count', [('40001', True, 2), ('40P01', True, 2),
    ('40001', False, 2), ('08006', False, 1)])
def test_expiry_retry_is_specific_bounded_and_has_one_effect(records, code, recover, attempt_count):
    actor, variant = records
    original = hold(actor, variant)
    actual_create = InventoryMovement.objects.create
    attempts = []

    def create_movement(**kwargs):
        attempts.append(kwargs)
        if recover and len(attempts) > 1:
            return actual_create(**kwargs)
        cause = RuntimeError('injected transaction failure')
        cause.sqlstate = code
        error = OperationalError('injected transaction failure')
        error.__cause__ = cause
        raise error

    with patch('web.inventory.expiry_service.InventoryMovement.objects.create', side_effect=create_movement):
        if recover:
            assert expire_due_reservations(actor=actor, now=DEADLINE).expired == 1
        else:
            with pytest.raises(OperationalError):
                expire_due_reservations(actor=actor, now=DEADLINE)
    assert len(attempts) == attempt_count
    assert InventoryMovement.objects.filter(kind='expire').count() == int(recover)
    if not recover:
        assert selectors.stock(actor=actor, variant_id=variant.pk) == original.stock
