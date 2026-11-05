from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection

from codex_ecommerce.inventory import (
    IdempotencyConflictError,
    InvalidTransitionError,
    OperationContext,
    StaleRevisionError,
)
from web.catalog.models import Brand, Category, Product, ProductVariant
from web.inventory import selectors, services
from web.inventory.models import InventoryMovement, StockBalance
from web.staff.models import StaffAuditEvent

pytestmark = [pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != 'postgresql', reason='Requires isolated PostgreSQL test database')]


@pytest.fixture
def records():
    actor = get_user_model().objects.create_user(username='concurrent-stock', is_staff=True, is_superuser=True)
    brand = Brand.objects.create(slug='concurrent-brand', name='Brand')
    category = Category.objects.create(slug='concurrent-category', name_key='category')
    product = Product.objects.create(slug='concurrent-product', model_name='Product', brand=brand, category=category)
    variants = [ProductVariant.objects.create(product=product, sku=f'CONCURRENT-{i}',
        color_code='black', color_name_key='black', size=str(i), price='10.00') for i in range(2)]
    return actor, variants


def ctx(actor, key, revision=0):
    return OperationContext(key, 'staff', str(actor.pk), 'Isolated concurrency QA', revision)


def command(method, actor, variant, quantity, context):
    return method(actor=actor, variant_id=variant.pk, quantity=quantity, context=context)


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
            except (StaleRevisionError, InvalidTransitionError, IdempotencyConflictError) as error:
                return backend, error
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=len(functions)) as executor:
        futures = [executor.submit(run, function) for function in functions]
        results = [future.result(timeout=20) for future in futures]
    assert len({backend for backend, _ in results}) == len(functions)
    return [result for _, result in results]


def test_concurrent_first_creation_different_keys(records):
    actor, (variant, _) = records
    results = race([lambda: command(services.initialize, actor, variant, 5, ctx(actor, 'init-a')),
        lambda: command(services.initialize, actor, variant, 8, ctx(actor, 'init-b'))])
    assert sum(isinstance(result, InvalidTransitionError) for result in results) == 1
    assert StockBalance.objects.count() == InventoryMovement.objects.count() == StaffAuditEvent.objects.count() == 1
    assert selectors.stock(actor=actor, variant_id=variant.pk).on_hand in (5, 8)


@pytest.mark.parametrize('method,quantities', [(services.initialize, (4, 4)), (services.receive, (3, 3))])
def test_concurrent_same_key_returns_exact_original_result_once(records, method, quantities):
    actor, (variant, _) = records
    revision = 0
    if method is services.receive:
        command(services.initialize, actor, variant, 4, ctx(actor, 'init'))
        revision = 1
    context = ctx(actor, 'shared', revision)
    results = race([lambda: command(method, actor, variant, quantities[0], context),
        lambda: command(method, actor, variant, quantities[1], context)])
    assert results[0] == results[1]
    assert InventoryMovement.objects.filter(operation_key='shared').count() == 1
    assert StaffAuditEvent.objects.count() == (1 if revision == 0 else 2)
    later = command(services.receive, actor, variant, 2, ctx(actor, 'later', results[0].revision))
    assert command(method, actor, variant, quantities[0], context) == results[0]
    assert selectors.stock(actor=actor, variant_id=variant.pk) == later


def test_concurrent_receipts_revision_conflict_then_explicit_retry(records):
    actor, (variant, _) = records
    command(services.initialize, actor, variant, 4, ctx(actor, 'init'))
    contexts = [ctx(actor, 'receipt-a', 1), ctx(actor, 'receipt-b', 1)]
    results = race([lambda: command(services.receive, actor, variant, 2, contexts[0]),
        lambda: command(services.receive, actor, variant, 3, contexts[1])])
    stale_index = next(i for i, result in enumerate(results) if isinstance(result, StaleRevisionError))
    assert sum(isinstance(result, StaleRevisionError) for result in results) == 1
    current = selectors.stock(actor=actor, variant_id=variant.pk)
    command(services.receive, actor, variant, (2, 3)[stale_index],
        replace(contexts[stale_index], expected_revision=current.revision))
    assert selectors.stock(actor=actor, variant_id=variant.pk).on_hand == 9
    assert InventoryMovement.objects.count() == StaffAuditEvent.objects.count() == 3


def test_concurrent_absolute_adjust_cannot_overwrite_newer_snapshot(records):
    actor, (variant, _) = records
    command(services.initialize, actor, variant, 8, ctx(actor, 'init'))
    results = race([lambda: command(services.adjust, actor, variant, 3, ctx(actor, 'count-a', 1)),
        lambda: command(services.adjust, actor, variant, 6, ctx(actor, 'count-b', 1))])
    assert sum(isinstance(result, StaleRevisionError) for result in results) == 1
    current = selectors.stock(actor=actor, variant_id=variant.pk)
    assert current.on_hand in (3, 6) and current.revision == 2
    assert InventoryMovement.objects.count() == StaffAuditEvent.objects.count() == 2


def test_shared_key_different_sku_rolls_back_loser_entire_transaction(records):
    actor, variants = records
    barrier = Barrier(2)
    real_calculate = services.initialize_stock

    def calculate(*args):
        # Force both independent target transactions past their initial scoped
        # key read; only the DB uniqueness claim can decide the winner.
        result = real_calculate(*args)
        barrier.wait(timeout=10)
        return result

    with patch('web.inventory.services.initialize_stock', side_effect=calculate):
        results = race([lambda: command(services.initialize, actor, variants[0], 4, ctx(actor, 'cross-sku')),
            lambda: command(services.initialize, actor, variants[1], 7, ctx(actor, 'cross-sku'))])
    assert sum(isinstance(result, IdempotencyConflictError) for result in results) == 1
    assert StockBalance.objects.count() == InventoryMovement.objects.count() == StaffAuditEvent.objects.count() == 1
    loser = next(i for i, result in enumerate(results) if isinstance(result, IdempotencyConflictError))
    assert selectors.stock(actor=actor, variant_id=variants[loser].pk) is None
