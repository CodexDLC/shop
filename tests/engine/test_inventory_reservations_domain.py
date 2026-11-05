from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from codex_ecommerce.inventory import (
    InsufficientStockError,
    InvalidQuantityError,
    InvalidTransitionError,
    InventoryInvariantError,
    OperationContext,
    ReservationExpiredError,
    ReservationResult,
    ReservationSnapshot,
    ReservationState,
    StaleRevisionError,
    StockKey,
    StockSnapshot,
    commit_reservation,
    fulfill_reservation,
    release_reservation,
    reserve_stock,
)

NOW = datetime(2026, 11, 1, 12, tzinfo=UTC)
DEADLINE = NOW + timedelta(minutes=30)
KEY = StockKey('1', 'main')


def ctx(revision):
    return OperationContext('operation', 'staff', '1', 'Domain QA', revision)


def held(quantity=5):
    return reserve_stock(StockSnapshot(KEY, 8, 0, 1), 'line-opaque', quantity, ctx(1),
        expires_at=DEADLINE, now=NOW)


def test_reserve_commit_partial_release_and_fulfill_conserve_both_snapshots():
    reserved = held()
    assert isinstance(reserved, ReservationResult)
    assert (reserved.stock.on_hand, reserved.stock.reserved, reserved.stock.revision) == (8, 5, 2)
    assert reserved.reservation.revision == 1 and reserved.reservation.state is ReservationState.HELD
    committed = commit_reservation(reserved.stock, reserved.reservation, ctx(2), expected_reservation_revision=1, now=NOW)
    assert (committed.stock.on_hand, committed.stock.reserved, committed.stock.revision) == (8, 5, 3)
    assert committed.reservation.expires_at is None and committed.reservation.revision == 2
    partial = fulfill_reservation(committed.stock, committed.reservation, 2, ctx(3), expected_reservation_revision=2, now=NOW)
    assert (partial.stock.on_hand, partial.stock.reserved) == (6, 3)
    assert partial.reservation.state is ReservationState.COMMITTED
    released = release_reservation(partial.stock, partial.reservation, 1, ctx(4), expected_reservation_revision=3, now=NOW)
    closed = fulfill_reservation(released.stock, released.reservation, 2, ctx(5), expected_reservation_revision=4, now=NOW)
    assert (closed.stock.on_hand, closed.stock.reserved, closed.stock.revision) == (4, 0, 6)
    assert (closed.reservation.original, closed.reservation.consumed, closed.reservation.released) == (5, 4, 1)
    assert closed.reservation.remaining_reserved == 0 and closed.reservation.revision == 5
    assert closed.reservation.state is ReservationState.CLOSED
    assert reserved.stock.on_hand == 8 and reserved.reservation.remaining_reserved == 5
    with pytest.raises(FrozenInstanceError):
        closed.reservation.revision = 9
    with pytest.raises(FrozenInstanceError):
        closed.stock = reserved.stock


def test_commit_expiry_boundary_utc_and_release_expired_hold():
    result = held()
    with pytest.raises(ReservationExpiredError):
        commit_reservation(result.stock, result.reservation, ctx(2), expected_reservation_revision=1, now=DEADLINE)
    other_zone = DEADLINE.astimezone(timezone(timedelta(hours=2)))
    with pytest.raises(ReservationExpiredError):
        commit_reservation(result.stock, result.reservation, ctx(2), expected_reservation_revision=1, now=other_zone)
    released = release_reservation(result.stock, result.reservation, 5, ctx(2), expected_reservation_revision=1, now=DEADLINE)
    assert released.reservation.state is ReservationState.CLOSED and released.stock.reserved == 0


@pytest.mark.parametrize('quantity', [0, -1, True, 1.5, '2', None])
def test_reservation_positive_exact_quantities(quantity):
    with pytest.raises(InvalidQuantityError):
        reserve_stock(StockSnapshot(KEY, 8, 0, 1), 'line', quantity, ctx(1), expires_at=DEADLINE, now=NOW)
    result = held()
    for transition in (release_reservation, fulfill_reservation):
        with pytest.raises(InvalidQuantityError):
            transition(result.stock, result.reservation, quantity, ctx(2), expected_reservation_revision=1, now=NOW)


def test_availability_revision_snapshot_and_transition_guards():
    with pytest.raises(InsufficientStockError):
        reserve_stock(StockSnapshot(KEY, 8, 6, 1), 'line', 3, ctx(1), expires_at=DEADLINE, now=NOW)
    result = held()
    with pytest.raises(StaleRevisionError):
        commit_reservation(result.stock, result.reservation, ctx(1), expected_reservation_revision=1, now=NOW)
    with pytest.raises(StaleRevisionError):
        commit_reservation(result.stock, result.reservation, ctx(2), expected_reservation_revision=0, now=NOW)
    for bad in (True, 1.0, -1):
        with pytest.raises(InvalidQuantityError):
            commit_reservation(result.stock, result.reservation, ctx(2), expected_reservation_revision=bad, now=NOW)
    with pytest.raises(InventoryInvariantError):
        commit_reservation(replace(result.stock, key=StockKey('2', 'main')), result.reservation,
            ctx(2), expected_reservation_revision=1, now=NOW)
    with pytest.raises(InventoryInvariantError):
        commit_reservation(replace(result.stock, reserved=0), result.reservation,
            ctx(2), expected_reservation_revision=1, now=NOW)
    with pytest.raises(InvalidTransitionError):
        fulfill_reservation(result.stock, result.reservation, 1, ctx(2), expected_reservation_revision=1, now=NOW)
    with pytest.raises(InvalidQuantityError):
        release_reservation(result.stock, result.reservation, 6, ctx(2), expected_reservation_revision=1, now=NOW)
    closed = release_reservation(result.stock, result.reservation, 5, ctx(2), expected_reservation_revision=1, now=NOW)
    for transition in (release_reservation, fulfill_reservation):
        with pytest.raises(InvalidTransitionError):
            transition(closed.stock, closed.reservation, 1, ctx(3), expected_reservation_revision=2, now=NOW)
    with pytest.raises(InvalidTransitionError):
        commit_reservation(closed.stock, closed.reservation, ctx(3), expected_reservation_revision=2, now=NOW)


def test_stale_revision_precedes_shortage_and_fresh_revision_reports_shortage():
    stock = StockSnapshot(KEY, 1, 1, 2)
    with pytest.raises(StaleRevisionError):
        reserve_stock(stock, 'another-line', 1, ctx(1), expires_at=DEADLINE, now=NOW)
    with pytest.raises(InsufficientStockError):
        reserve_stock(stock, 'another-line', 1, ctx(2), expires_at=DEADLINE, now=NOW)


def test_deadline_and_now_are_aware_and_deadline_is_future():
    for now, expiry in ((NOW.replace(tzinfo=None), DEADLINE), (NOW, DEADLINE.replace(tzinfo=None))):
        with pytest.raises(InventoryInvariantError):
            reserve_stock(StockSnapshot(KEY, 8, 0, 1), 'line', 1, ctx(1), expires_at=expiry, now=now)
    for expiry in (NOW, NOW - timedelta(seconds=1)):
        with pytest.raises(ReservationExpiredError):
            reserve_stock(StockSnapshot(KEY, 8, 0, 1), 'line', 1, ctx(1), expires_at=expiry, now=NOW)


def test_existing_snapshot_positional_api_preserved_with_default_revision():
    snapshot = ReservationSnapshot('legacy-line', KEY, 2, 2, 0, 0, ReservationState.HELD, DEADLINE)
    assert snapshot.revision == 0
    with pytest.raises(InvalidQuantityError):
        replace(snapshot, revision=True)
