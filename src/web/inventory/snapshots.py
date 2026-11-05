from datetime import datetime

from codex_ecommerce.inventory import (
    InventoryInvariantError,
    ReservationResult,
    ReservationSnapshot,
    ReservationState,
    StockKey,
    StockSnapshot,
)


def balance_snapshot(balance):
    if balance is None:
        return None
    return StockSnapshot(StockKey(str(balance.variant_id), balance.location_id),
        balance.on_hand, balance.reserved, balance.revision)


def movement_snapshot(movement):
    stock = StockSnapshot(StockKey(str(movement.variant_id), movement.location_id),
        movement.after_on_hand, movement.after_reserved, movement.revision)
    if movement.kind in ('initialize', 'receive', 'adjust', 'external_snapshot'):
        if movement.reservation_id is not None or movement.after_reservation is not None:
            raise InventoryInvariantError()
        return stock
    if movement.kind not in ('reserve', 'commit', 'release', 'fulfill', 'expire', 'checked_return'):
        raise InventoryInvariantError()
    reservation = decode_reservation(movement.after_reservation)
    if (reservation.reservation_id != movement.reservation_id or reservation.revision < 1
            or type(movement.expected_reservation_revision) is not int
            or reservation.revision != movement.expected_reservation_revision + 1):
        raise InventoryInvariantError()
    if movement.kind == 'reserve':
        if movement.before_reservation is not None or movement.expected_reservation_revision != 0:
            raise InventoryInvariantError()
    else:
        before = decode_reservation(movement.before_reservation)
        if (before.reservation_id != reservation.reservation_id or before.key != reservation.key
                or before.original != reservation.original or before.revision != movement.expected_reservation_revision):
            raise InventoryInvariantError()
    return ReservationResult(stock, reservation)


def reservation_snapshot(reservation):
    if reservation is None:
        return None
    return ReservationSnapshot(reservation.reference,
        StockKey(str(reservation.variant_id), reservation.location_id), reservation.original,
        reservation.remaining_reserved, reservation.consumed, reservation.released,
        ReservationState(reservation.state), reservation.expires_at, reservation.revision, reservation.returned)


def encode_reservation(reservation):
    if reservation is None:
        return None
    return dict(reservation_id=reservation.reservation_id, variant_id=reservation.key.variant_id,
        location_id=reservation.key.location_id, original=reservation.original,
        remaining_reserved=reservation.remaining_reserved, consumed=reservation.consumed,
        released=reservation.released, state=reservation.state.value,
        expires_at=reservation.expires_at.isoformat() if reservation.expires_at is not None else None,
        revision=reservation.revision, returned=reservation.returned)


def decode_reservation(data):
    fields = {'reservation_id', 'variant_id', 'location_id', 'original', 'remaining_reserved',
        'consumed', 'released', 'state', 'expires_at', 'revision'}
    if not isinstance(data, dict) or set(data) not in (fields, fields | {'returned'}):
        raise InventoryInvariantError()
    try:
        expires_at = datetime.fromisoformat(data['expires_at']) if data['expires_at'] is not None else None
        state = ReservationState(data['state'])
    except (ValueError, TypeError) as error:
        raise InventoryInvariantError() from error
    return ReservationSnapshot(data['reservation_id'], StockKey(data['variant_id'], data['location_id']),
        data['original'], data['remaining_reserved'], data['consumed'], data['released'],
        state, expires_at, data['revision'], data.get('returned', 0))
