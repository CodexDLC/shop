from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from codex_ecommerce.inventory import (
    InvalidQuantityError,
    InvalidTransitionError,
    InventoryInvariantError,
    OperationContext,
    ReservationState,
    StaleRevisionError,
    StockKey,
    StockSnapshot,
    commit_reservation,
    expire_reservation,
    fulfill_reservation,
    release_reservation,
    reserve_stock,
)

NOW = datetime(2026, 11, 1, 12, tzinfo=UTC)
DEADLINE = NOW + timedelta(minutes=30)


def ctx(revision):
    return OperationContext('expiry', 'inventory_expiry', 'system', 'Reservation deadline reached', revision)


def held():
    return reserve_stock(StockSnapshot(StockKey('1', 'main'), 8, 0, 1), 'line', 5, ctx(1),
        expires_at=DEADLINE, now=NOW)


def test_expire_boundary_releases_remaining_without_consuming_stock():
    initial = held()
    partial = release_reservation(initial.stock, initial.reservation, 2, ctx(2),
        expected_reservation_revision=1, now=NOW)
    result = expire_reservation(partial.stock, partial.reservation, ctx(3),
        expected_reservation_revision=2, now=DEADLINE)
    assert (result.stock.on_hand, result.stock.reserved, result.stock.revision) == (8, 0, 4)
    assert (result.reservation.original, result.reservation.released, result.reservation.consumed) == (5, 5, 0)
    assert result.reservation.state is ReservationState.CLOSED
    assert result.reservation.expires_at is None and result.reservation.revision == 3
    assert partial.reservation.remaining_reserved == 3


def test_expiry_uses_utc_instant_and_requires_due_held():
    initial = held()
    with pytest.raises(InvalidTransitionError):
        expire_reservation(initial.stock, initial.reservation, ctx(2), expected_reservation_revision=1,
            now=DEADLINE - timedelta(microseconds=1))
    other_zone = DEADLINE.astimezone(timezone(timedelta(hours=2)))
    result = expire_reservation(initial.stock, initial.reservation, ctx(2),
        expected_reservation_revision=1, now=other_zone)
    assert result.stock.reserved == 0
    committed = commit_reservation(initial.stock, initial.reservation, ctx(2),
        expected_reservation_revision=1, now=NOW)
    partial = fulfill_reservation(committed.stock, committed.reservation, 2, ctx(3),
        expected_reservation_revision=2, now=NOW)
    for snapshot in (committed, partial, result):
        with pytest.raises(InvalidTransitionError):
            expire_reservation(snapshot.stock, snapshot.reservation, ctx(snapshot.stock.revision),
                expected_reservation_revision=snapshot.reservation.revision, now=DEADLINE)


def test_expire_validates_versions_snapshot_and_aware_time():
    initial = held()
    for context, revision in ((ctx(1), 1), (ctx(2), 0)):
        with pytest.raises(StaleRevisionError):
            expire_reservation(initial.stock, initial.reservation, context,
                expected_reservation_revision=revision, now=DEADLINE)
    for revision in (True, 1.0, -1):
        with pytest.raises(InvalidQuantityError):
            expire_reservation(initial.stock, initial.reservation, ctx(2),
                expected_reservation_revision=revision, now=DEADLINE)
    for now in (None, DEADLINE.replace(tzinfo=None)):
        with pytest.raises(InventoryInvariantError):
            expire_reservation(initial.stock, initial.reservation, ctx(2), expected_reservation_revision=1, now=now)
    with pytest.raises(InventoryInvariantError):
        expire_reservation(replace(initial.stock, reserved=0), initial.reservation, ctx(2),
            expected_reservation_revision=1, now=DEADLINE)
