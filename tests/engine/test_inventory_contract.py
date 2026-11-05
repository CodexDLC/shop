from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from codex_ecommerce.inventory import (
    InvalidQuantityError,
    InventoryInvariantError,
    OperationContext,
    OperationKind,
    ReservationSnapshot,
    ReservationState,
    StockKey,
    StockNotConfiguredError,
    StockSnapshot,
    require_stock,
)


def test_stock_bounds_and_missing_distinct_from_zero():
    key = StockKey('variant', 'location')
    stock = StockSnapshot(key, 0, 0, 0)
    assert require_stock(stock).available == 0
    with pytest.raises(StockNotConfiguredError):
        require_stock(None)
    with pytest.raises(InventoryInvariantError):
        StockSnapshot(key, 1, 2, 0)
    for value in (-1, True, 1.5):
        with pytest.raises(InvalidQuantityError):
            StockSnapshot(key, value, 0, 0)
    with pytest.raises(FrozenInstanceError):
        stock.on_hand = 2


def test_reservation_conservation_and_states():
    key = StockKey('v', 'l')
    expiry = datetime(2026, 11, 1, tzinfo=UTC)
    held = ReservationSnapshot('r', key, 5, 2, 0, 3, ReservationState.HELD, expiry)
    assert not held.is_expired(expiry - timedelta(microseconds=1))
    assert held.is_expired(expiry)
    with pytest.raises(InventoryInvariantError):
        ReservationSnapshot('r', key, 5, 2, 1, 1, ReservationState.HELD, expiry)
    with pytest.raises(InventoryInvariantError):
        ReservationSnapshot('r', key, 5, 2, 1, 2, ReservationState.COMMITTED, expiry)
    with pytest.raises(InventoryInvariantError):
        ReservationSnapshot('r', key, 5, 2, 1, 2, ReservationState.CLOSED, None)
    assert not ReservationSnapshot('r', key, 5, 2, 1, 2, ReservationState.COMMITTED, None).is_expired(expiry)
    assert not ReservationSnapshot('r', key, 5, 0, 3, 2, ReservationState.CLOSED, None).is_expired(expiry)
    with pytest.raises(InventoryInvariantError):
        ReservationSnapshot('r', key, 5, 2, 0, 3, ReservationState.HELD, expiry.replace(tzinfo=None))
    with pytest.raises(InventoryInvariantError):
        held.is_expired(expiry.replace(tzinfo=None))


def test_context_and_operations_are_explicit():
    ctx = OperationContext('key', 'source', 'owner', 'reason', 0)
    assert ctx.expected_revision == 0
    assert {x.value for x in OperationKind} >= {'receive', 'adjust', 'reserve', 'commit', 'release', 'expire', 'fulfill', 'checked_return'}
    with pytest.raises(InventoryInvariantError):
        OperationContext('', 'source', 'owner', 'reason', 0)
    with pytest.raises(InvalidQuantityError):
        OperationContext('key', 'source', 'owner', 'reason', True)
    assert StockNotConfiguredError.code == 'stock_not_configured'


def test_held_cannot_consume_and_closed_has_no_expiry():
    key = StockKey('v', 'l')
    expiry = datetime(2026, 11, 1, tzinfo=UTC)
    with pytest.raises(InventoryInvariantError):
        ReservationSnapshot('r', key, 3, 2, 1, 0, ReservationState.HELD, expiry)
    with pytest.raises(InventoryInvariantError):
        ReservationSnapshot('r', key, 3, 0, 0, 3, ReservationState.CLOSED, expiry)


def test_availability_check_is_snapshot_only():
    from codex_ecommerce.inventory import InsufficientStockError, require_available

    stock = StockSnapshot(StockKey('v', 'l'), 3, 2, 4)
    assert require_available(stock, 1) is stock
    with pytest.raises(InsufficientStockError):
        require_available(stock, 2)
    for value in (0, -1, True, 1.5):
        with pytest.raises(InvalidQuantityError):
            require_available(stock, value)


def test_all_quantity_fields_reject_nonintegers_and_invalid_state():
    key = StockKey('v', 'l')
    for index in range(4):
        for bad in (-1, False, 0.5):
            quantities = [3, 1, 1, 1]
            quantities[index] = bad
            with pytest.raises(InvalidQuantityError):
                ReservationSnapshot('r', key, *quantities, ReservationState.COMMITTED, None)
    with pytest.raises(InventoryInvariantError):
        ReservationSnapshot('r', key, 3, 1, 1, 1, 'committed', None)
    with pytest.raises(InventoryInvariantError):
        ReservationSnapshot('r', key, 0, 0, 0, 0, ReservationState.CLOSED, None)
    with pytest.raises(InventoryInvariantError):
        StockKey('', 'location')


def test_error_codes_are_stable_and_distinct():
    from codex_ecommerce.inventory import (
        IdempotencyConflictError,
        InsufficientStockError,
        InvalidTransitionError,
        ReservationExpiredError,
        StaleRevisionError,
    )

    errors = [InvalidQuantityError, InventoryInvariantError, StockNotConfiguredError,
              IdempotencyConflictError, InsufficientStockError, InvalidTransitionError,
              ReservationExpiredError, StaleRevisionError]
    assert [error.code for error in errors] == [
        'invalid_quantity', 'inventory_invariant', 'stock_not_configured',
        'idempotency_conflict', 'insufficient_stock', 'invalid_transition',
        'reservation_expired', 'stale_revision',
    ]
    assert all(error().action for error in errors)


def test_timezone_boundary_and_immutability():
    from datetime import timezone

    key = StockKey('v', 'l')
    expiry = datetime(2026, 11, 1, 12, tzinfo=UTC)
    held = ReservationSnapshot('r', key, 2, 2, 0, 0, ReservationState.HELD, expiry)
    assert held.is_expired(expiry.astimezone(timezone(timedelta(hours=2))))
    with pytest.raises(FrozenInstanceError):
        held.remaining_reserved = 0


def test_inventory_imports_are_framework_free():
    import ast
    from pathlib import Path

    inventory = Path(__file__).resolve().parents[2] / 'src' / 'codex_ecommerce' / 'inventory'
    forbidden = {'django', 'arq', 'redis', 'requests', 'httpx', 'celery'}
    for path in inventory.glob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name.split('.')[0] not in forbidden for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                assert node.module.split('.')[0] not in forbidden


def test_expiry_uses_instant_across_repeated_wall_time():
    from datetime import tzinfo

    class RepeatedHour(tzinfo):
        def utcoffset(self, dt):
            return timedelta(hours=1 if dt.fold else 2)

    zone = RepeatedHour()
    expiry = datetime(2026, 10, 25, 2, 30, tzinfo=zone, fold=1)
    earlier = datetime(2026, 10, 25, 2, 45, tzinfo=zone, fold=0)
    held = ReservationSnapshot('r', StockKey('v', 'l'), 1, 1, 0, 0, ReservationState.HELD, expiry)
    assert not held.is_expired(earlier)
    assert held.is_expired(expiry)
