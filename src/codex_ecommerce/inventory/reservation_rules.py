from dataclasses import replace
from datetime import UTC, datetime

from .invalid_quantity import InvalidQuantityError
from .invalid_transition import InvalidTransitionError
from .inventory_invariant import InventoryInvariantError
from .operation_context import OperationContext
from .reservation_expired import ReservationExpiredError
from .reservation_result import ReservationResult
from .reservation_snapshot import ReservationSnapshot
from .reservation_state import ReservationState
from .stale_revision import StaleRevisionError
from .stock_rules import require_available, require_stock
from .validation import aware_datetime, nonnegative_int


def _context(context, stock):
    if not isinstance(context, OperationContext):
        raise InventoryInvariantError()
    if context.expected_revision != stock.revision:
        raise StaleRevisionError()


def _positive(quantity):
    nonnegative_int(quantity)
    if quantity == 0:
        raise InvalidQuantityError()


def _snapshots(stock, reservation, context, expected_reservation_revision, now):
    stock = require_stock(stock)
    aware_datetime(now)
    nonnegative_int(expected_reservation_revision)
    ReservationResult(stock, reservation)
    _context(context, stock)
    if reservation.revision != expected_reservation_revision:
        raise StaleRevisionError()
    return stock


def reserve_stock(stock, reservation_id, quantity, context, *, expires_at: datetime, now: datetime):
    """Calculate a new hold; persistence must guarantee reference uniqueness."""
    _positive(quantity)
    stock = require_stock(stock)
    _context(context, stock)
    require_available(stock, quantity)
    aware_datetime(now)
    aware_datetime(expires_at)
    if now.astimezone(UTC) >= expires_at.astimezone(UTC):
        raise ReservationExpiredError()
    reservation = ReservationSnapshot(reservation_id, stock.key, quantity, quantity, 0, 0,
        ReservationState.HELD, expires_at.astimezone(UTC), 1)
    return ReservationResult(replace(stock, reserved=stock.reserved + quantity, revision=stock.revision + 1), reservation)


def commit_reservation(stock, reservation, context, *, expected_reservation_revision, now):
    stock = _snapshots(stock, reservation, context, expected_reservation_revision, now)
    if reservation.state is not ReservationState.HELD:
        raise InvalidTransitionError()
    if reservation.is_expired(now):
        raise ReservationExpiredError()
    return ReservationResult(replace(stock, revision=stock.revision + 1),
        replace(reservation, state=ReservationState.COMMITTED, expires_at=None, revision=reservation.revision + 1))


def release_reservation(stock, reservation, quantity, context, *, expected_reservation_revision, now):
    _positive(quantity)
    stock = _snapshots(stock, reservation, context, expected_reservation_revision, now)
    if reservation.state not in (ReservationState.HELD, ReservationState.COMMITTED):
        raise InvalidTransitionError()
    if quantity > reservation.remaining_reserved:
        raise InvalidQuantityError()
    remaining = reservation.remaining_reserved - quantity
    after = replace(reservation, remaining_reserved=remaining, released=reservation.released + quantity,
        revision=reservation.revision + 1,
        state=reservation.state if remaining else ReservationState.CLOSED,
        expires_at=reservation.expires_at if remaining else None)
    return ReservationResult(replace(stock, reserved=stock.reserved - quantity, revision=stock.revision + 1), after)


def fulfill_reservation(stock, reservation, quantity, context, *, expected_reservation_revision, now):
    _positive(quantity)
    stock = _snapshots(stock, reservation, context, expected_reservation_revision, now)
    if reservation.state is not ReservationState.COMMITTED:
        raise InvalidTransitionError()
    if quantity > reservation.remaining_reserved:
        raise InvalidQuantityError()
    remaining = reservation.remaining_reserved - quantity
    after = replace(reservation, remaining_reserved=remaining, consumed=reservation.consumed + quantity,
        revision=reservation.revision + 1,
        state=ReservationState.COMMITTED if remaining else ReservationState.CLOSED)
    return ReservationResult(replace(stock, on_hand=stock.on_hand - quantity,
        reserved=stock.reserved - quantity, revision=stock.revision + 1), after)


def expire_reservation(stock, reservation, context, *, expected_reservation_revision, now):
    """Release the entire remaining due hold; committed obligations never expire."""
    stock = _snapshots(stock, reservation, context, expected_reservation_revision, now)
    if reservation.state is not ReservationState.HELD or not reservation.is_expired(now):
        raise InvalidTransitionError()
    return release_reservation(stock, reservation, reservation.remaining_reserved, context,
        expected_reservation_revision=expected_reservation_revision, now=now)


def checked_return_reservation(stock, reservation, quantity, context, *,
        expected_reservation_revision, now, received, inspected):
    """Accept inspected physical stock; never undo historical fulfillment."""
    _positive(quantity)
    stock = _snapshots(stock, reservation, context, expected_reservation_revision, now)
    if received is not True or inspected is not True:
        raise InvalidTransitionError()
    if quantity > reservation.consumed - reservation.returned:
        raise InvalidQuantityError()
    return ReservationResult(replace(stock, on_hand=stock.on_hand + quantity, revision=stock.revision + 1),
        replace(reservation, returned=reservation.returned + quantity, revision=reservation.revision + 1))
