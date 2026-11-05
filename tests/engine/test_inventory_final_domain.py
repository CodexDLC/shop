from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime

import pytest

from codex_ecommerce.inventory import (
    InvalidQuantityError,
    InvalidTransitionError,
    InventoryChanged,
    InventoryInvariantError,
    OperationContext,
    ReservationSnapshot,
    ReservationState,
    StockKey,
    StockSnapshot,
    checked_return_reservation,
)

NOW = datetime(2026, 11, 5, tzinfo=UTC)
KEY = StockKey('1', 'main')


def test_checked_return_preserves_historical_conservation_and_closed_state():
    line = ReservationSnapshot('test-line', KEY, 5, 0, 3, 2, ReservationState.CLOSED, None, 4)
    stock = StockSnapshot(KEY, 2, 0, 5)
    result = checked_return_reservation(stock, line, 2,
        OperationContext('return', 'staff', '1', 'TEST received and inspected', 5),
        expected_reservation_revision=4, now=NOW, received=True, inspected=True)
    assert (result.stock.on_hand, result.stock.reserved, result.stock.revision) == (4, 0, 6)
    assert (result.reservation.original, result.reservation.consumed, result.reservation.released) == (5, 3, 2)
    assert result.reservation.returned == 2 and result.reservation.revision == 5
    assert result.reservation.state is ReservationState.CLOSED and result.reservation.expires_at is None
    assert line.returned == 0
    with pytest.raises(InvalidQuantityError):
        checked_return_reservation(result.stock, result.reservation, 2,
            OperationContext('excess', 'staff', '1', 'TEST', 6),
            expected_reservation_revision=5, now=NOW, received=True, inspected=True)


@pytest.mark.parametrize('received,inspected', [(False, True), (True, False), (1, True), (True, 'yes')])
def test_return_requires_explicit_true_attestations(received, inspected):
    line = ReservationSnapshot('line', KEY, 1, 0, 1, 0, ReservationState.CLOSED, None, 3)
    with pytest.raises(InvalidTransitionError):
        checked_return_reservation(StockSnapshot(KEY, 0, 0, 4), line, 1,
            OperationContext('return', 'staff', '1', 'TEST', 4), expected_reservation_revision=3,
            now=NOW, received=received, inspected=inspected)
    with pytest.raises(InventoryInvariantError):
        replace(line, returned=2)


def test_inventory_changed_is_immutable_safe_versioned_value():
    event = InventoryChanged('event-1', 1, 8, StockSnapshot(KEY, 3, 1, 4), NOW)
    assert event.event_type == 'inventory_changed'
    assert event.payload() == dict(event_id='event-1', event_type='inventory_changed', version=1,
        movement_id=8, variant_id='1', location_id='main', revision=4,
        on_hand=3, reserved=1, available=2, occurred_at=NOW.isoformat())
    with pytest.raises(FrozenInstanceError):
        event.version = 2
