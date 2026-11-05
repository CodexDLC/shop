from dataclasses import replace
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, OperationalError, connection, transaction
from django.db.models.deletion import ProtectedError
from django.test.utils import CaptureQueriesContext

from codex_ecommerce.inventory import (
    IdempotencyConflictError,
    InvalidTransitionError,
    InventoryInvariantError,
    OperationContext,
    StaleRevisionError,
    StockNotConfiguredError,
)
from web.catalog.models import Brand, Category, Product, ProductVariant
from web.inventory import selectors, services
from web.inventory.models import InventoryMovement, StockBalance
from web.staff.models import StaffAuditEvent

pytestmark = pytest.mark.django_db


@pytest.fixture
def actor():
    return get_user_model().objects.create_user(username='stock-owner', is_staff=True, is_superuser=True)


@pytest.fixture
def variant():
    brand = Brand.objects.create(slug='stock-brand', name='Stock brand')
    category = Category.objects.create(slug='stock-category', name_key='stock.category')
    product = Product.objects.create(slug='stock-product', model_name='Stock product', brand=brand, category=category)
    return ProductVariant.objects.create(product=product, sku='STOCK-1', color_code='black',
        color_name_key='black', size='M', price='10.00', demo_quantity=92)


def context(actor, key='initial', revision=0):
    return OperationContext(key, 'staff', str(actor.pk), 'Verified warehouse count', revision)


def invoke(command, actor, variant, quantity, ctx):
    return command(actor=actor, variant_id=variant.pk, quantity=quantity, context=ctx)


def test_explicit_initialization_receipt_adjust_ledger_and_original_replay(actor, variant):
    assert selectors.stock(actor=actor, variant_id=variant.pk) is None
    ctx = context(actor)
    first = invoke(services.initialize, actor, variant, 0, ctx)
    receipt = invoke(services.receive, actor, variant, 7, context(actor, 'receipt', 1))
    final = invoke(services.adjust, actor, variant, 5, context(actor, 'count', 2))
    assert invoke(services.initialize, actor, variant, 0, ctx) == first
    assert invoke(services.receive, actor, variant, 7, context(actor, 'receipt', 1)) == receipt
    assert selectors.stock(actor=actor, variant_id=variant.pk) == final
    assert InventoryMovement.objects.count() == StaffAuditEvent.objects.count() == 3
    entry = InventoryMovement.objects.get(kind='adjust')
    assert (entry.before_on_hand, entry.after_on_hand, entry.delta_on_hand) == (7, 5, -2)
    assert entry.created_at.utcoffset().total_seconds() == 0
    variant.refresh_from_db()
    assert variant.demo_quantity == 92


@pytest.mark.parametrize('change', ['quantity', 'reason', 'revision', 'kind', 'target'])
def test_scoped_key_conflicts_for_every_payload_dimension(actor, variant, change):
    ctx = context(actor)
    invoke(services.initialize, actor, variant, 3, ctx)
    command, qty, target = services.initialize, 3, variant
    if change == 'quantity':
        qty = 4
    elif change == 'reason':
        ctx = replace(ctx, reason='Different count')
    elif change == 'revision':
        ctx = replace(ctx, expected_revision=1)
    elif change == 'kind':
        command = services.receive
    else:
        target = ProductVariant.objects.create(product=variant.product, sku='STOCK-2', color_code='black',
            color_name_key='black', size='L', price='10.00')
    with pytest.raises(IdempotencyConflictError):
        invoke(command, actor, target, qty, ctx)
    assert StockBalance.objects.count() == InventoryMovement.objects.count() == 1


@pytest.mark.parametrize('command', [services.receive, services.adjust])
def test_unconfigured_stock_not_silently_initialized(actor, variant, command):
    with pytest.raises(StockNotConfiguredError):
        invoke(command, actor, variant, 4, context(actor))
    assert not InventoryMovement.objects.exists()


def test_stale_revision_and_unknown_inactive_location_rejected(actor, variant):
    invoke(services.initialize, actor, variant, 4, context(actor))
    with pytest.raises(InvalidTransitionError):
        invoke(services.initialize, actor, variant, 4, context(actor, 'again'))
    with pytest.raises(StaleRevisionError):
        invoke(services.adjust, actor, variant, 3, context(actor, 'count', 0))
    for kwargs in ({'variant_id': 999999}, {'location_id': 'unknown'}):
        args = dict(actor=actor, variant_id=variant.pk, quantity=4, context=context(actor, 'bad', 1))
        args.update(kwargs)
        with pytest.raises(InventoryInvariantError):
            services.receive(**args)
    variant.is_active = False
    variant.save()
    with pytest.raises(InventoryInvariantError):
        invoke(services.receive, actor, variant, 2, context(actor, 'inactive', 1))


def test_permissions_trusted_context_and_replay_authorization(actor, variant):
    invoke(services.initialize, actor, variant, 4, context(actor))
    for forged in (replace(context(actor), source='ebay'), replace(context(actor), owner='another')):
        with pytest.raises(PermissionDenied):
            invoke(services.initialize, actor, variant, 4, forged)
    actor.is_superuser = False
    actor.save()
    for command in (services.initialize, services.receive, services.adjust):
        with pytest.raises(PermissionDenied):
            invoke(command, actor, variant, 4, context(actor))
    for selector in (selectors.balances, selectors.history):
        with pytest.raises(PermissionDenied):
            selector(actor=actor)
    actor.user_permissions.add(Permission.objects.get(content_type__app_label='inventory', codename='receive_stockbalance'))
    invoke(services.receive, actor, variant, 2, context(actor, 'receipt', 1))
    with pytest.raises(PermissionDenied):
        invoke(services.adjust, actor, variant, 3, context(actor, 'count', 2))
    actor.is_active = False
    actor.save()
    with pytest.raises(PermissionDenied):
        invoke(services.receive, actor, variant, 2, context(actor, 'receipt', 1))


def test_failure_rolls_back_balance_ledger_key_and_audit(actor, variant):
    with patch('web.inventory.services.StaffAuditEvent.objects.create', side_effect=RuntimeError('injected')):
        with pytest.raises(RuntimeError, match='injected'):
            invoke(services.initialize, actor, variant, 4, context(actor))
    assert not StockBalance.objects.exists() and not InventoryMovement.objects.exists()
    invoke(services.initialize, actor, variant, 4, context(actor))
    with patch('web.inventory.services.InventoryMovement.objects.create', side_effect=RuntimeError('injected')):
        with pytest.raises(RuntimeError):
            invoke(services.receive, actor, variant, 2, context(actor, 'receipt', 1))
    assert selectors.stock(actor=actor, variant_id=variant.pk).on_hand == 4
    assert InventoryMovement.objects.count() == StaffAuditEvent.objects.count() == 1


def test_normal_orm_guards_and_variant_protection(actor, variant):
    invoke(services.initialize, actor, variant, 4, context(actor))
    entry = InventoryMovement.objects.get()
    for mutation in (lambda: entry.save(), lambda: entry.delete(),
            lambda: InventoryMovement.objects.update(reason='changed'),
            lambda: InventoryMovement.objects.all().delete(),
            lambda: InventoryMovement.objects.bulk_update([entry], ['reason']),
            lambda: InventoryMovement._base_manager.update(reason='changed'),
            lambda: InventoryMovement.objects.bulk_create([InventoryMovement()]),
            lambda: StockBalance.objects.update(on_hand=999),
            lambda: StockBalance.objects.get().save(),
            lambda: StockBalance.objects.get().delete(),
            lambda: StockBalance.objects.bulk_update([StockBalance.objects.get()], ['on_hand'])):
        with pytest.raises(PermissionDenied):
            mutation()
    with pytest.raises(ProtectedError):
        variant.delete()
    with pytest.raises(ProtectedError):
        actor.delete()


def test_db_constraints_and_bounded_reads(actor, variant):
    invoke(services.initialize, actor, variant, 4, context(actor))
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('UPDATE inventory_stockbalance SET reserved = 5')
    for limit in (0, 101, True):
        with pytest.raises(InventoryInvariantError):
            selectors.history(actor=actor, limit=limit)
    with CaptureQueriesContext(connection) as queries:
        page = selectors.history(actor=actor, limit=1)
        assert page[0].after_on_hand == 4
        assert page[0].variant.sku == variant.sku
    assert len(queries) <= 2


def test_single_action_and_read_permissions_are_independent(actor, variant):
    invoke(services.initialize, actor, variant, 4, context(actor))
    actor.is_superuser = False
    actor.save()
    actor.user_permissions.add(Permission.objects.get(content_type__app_label='inventory', codename='view_stockbalance'))
    assert selectors.stock(actor=actor, variant_id=variant.pk).on_hand == 4
    assert len(selectors.balances(actor=actor)) == 1
    with pytest.raises(PermissionDenied):
        selectors.history(actor=actor)
    actor.user_permissions.add(Permission.objects.get(content_type__app_label='inventory', codename='view_inventorymovement'))
    assert len(selectors.history(actor=actor)) == 1
    with pytest.raises(PermissionDenied):
        invoke(services.initialize, actor, variant, 4, context(actor))
    actor.is_staff = False
    actor.save()
    with pytest.raises(PermissionDenied):
        selectors.history(actor=actor)


@pytest.mark.parametrize('bad_id', [True, '1', 0, -1, None])
def test_read_ids_are_validated(actor, bad_id):
    with pytest.raises(InventoryInvariantError):
        selectors.stock(actor=actor, variant_id=bad_id)
    if bad_id is not None:
        with pytest.raises(InventoryInvariantError):
            selectors.history(actor=actor, variant_id=bad_id)


def test_replay_survives_variant_deactivation_but_not_permission_revocation(actor, variant):
    ctx = context(actor)
    first = invoke(services.initialize, actor, variant, 4, ctx)
    variant.is_active = False
    variant.save()
    assert invoke(services.initialize, actor, variant, 4, ctx) == first
    actor.is_superuser = False
    actor.save()
    with pytest.raises(PermissionDenied):
        invoke(services.initialize, actor, variant, 4, ctx)


def test_reserved_stock_not_erased_and_unexpected_integrity_not_hidden(actor, variant):
    invoke(services.initialize, actor, variant, 4, context(actor))
    # A fixture for a future reservation owner, not a public mutation route.
    with connection.cursor() as cursor:
        cursor.execute('UPDATE inventory_stockbalance SET reserved = 3')
    with pytest.raises(InventoryInvariantError):
        invoke(services.adjust, actor, variant, 2, context(actor, 'count', 1))
    with patch('web.inventory.services.InventoryMovement.objects.create', side_effect=IntegrityError('unrelated')):
        with pytest.raises(IntegrityError, match='unrelated'):
            invoke(services.adjust, actor, variant, 3, context(actor, 'count', 1))
    assert selectors.stock(actor=actor, variant_id=variant.pk).on_hand == 4
    assert InventoryMovement.objects.count() == 1


def test_read_query_budget_does_not_grow_with_list_size(actor, variant):
    invoke(services.initialize, actor, variant, 4, context(actor))
    for index in range(4):
        invoke(services.receive, actor, variant, 1, context(actor, f'receipt-{index}', index + 1))
    counts = []
    for limit in (1, 5):
        with CaptureQueriesContext(connection) as queries:
            rows = selectors.history(actor=actor, limit=limit)
            assert len(rows) == limit
            assert all(row.variant.sku == variant.sku for row in rows)
        counts.append(len(queries))
    assert counts == [2, 2]


def database_failure(code):
    cause = RuntimeError('injected database failure')
    cause.sqlstate = code
    error = OperationalError('injected database failure')
    error.__cause__ = cause
    return error


@pytest.mark.parametrize('code', ['40001', '40P01'])
def test_aborted_transaction_retries_once_with_no_duplicate_effect(actor, variant, code):
    invoke(services.initialize, actor, variant, 4, context(actor))
    real_create = InventoryMovement.objects.create
    attempts = []

    def create_movement(**kwargs):
        attempts.append(kwargs)
        if len(attempts) == 1:
            raise database_failure(code)
        return real_create(**kwargs)

    with patch('web.inventory.services.InventoryMovement.objects.create', side_effect=create_movement):
        result = invoke(services.receive, actor, variant, 2, context(actor, 'receipt', 1))
    assert len(attempts) == 2
    assert result.on_hand == 6 and result.revision == 2
    assert InventoryMovement.objects.count() == StaffAuditEvent.objects.count() == 2


@pytest.mark.parametrize('code,attempt_count', [('40001', 2), ('40P01', 2), ('08006', 1), (None, 1)])
def test_transient_retry_is_bounded_and_other_database_errors_propagate(actor, variant, code, attempt_count):
    invoke(services.initialize, actor, variant, 4, context(actor))

    def fail_create(**kwargs):
        raise database_failure(code)

    with patch('web.inventory.services.InventoryMovement.objects.create',
            side_effect=fail_create) as create:
        with pytest.raises(OperationalError):
            invoke(services.receive, actor, variant, 2, context(actor, 'receipt', 1))
    assert create.call_count == attempt_count
    assert selectors.stock(actor=actor, variant_id=variant.pk).on_hand == 4
    assert InventoryMovement.objects.count() == StaffAuditEvent.objects.count() == 1
