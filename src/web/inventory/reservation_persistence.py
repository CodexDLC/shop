"""Concrete shared write path for validated staff and checkout transitions."""
from django.db import connection

from codex_ecommerce.inventory import InvalidQuantityError, InventoryInvariantError
from web.staff.models import StaffAuditEvent

from .models import InventoryMovement
from .operation_store import MAX_INT, fingerprint
from .snapshots import encode_reservation
from .write_access import require_service_write


def persist_reservation_result(*, actor, kind, context, balance, line, result,
        before_stock, before_line, quantity, now):
    require_service_write()
    if not connection.in_atomic_block:
        raise InventoryInvariantError()
    after, reservation = result.stock, result.reservation
    for value in (after.on_hand, after.reserved, after.revision, reservation.original,
            reservation.remaining_reserved, reservation.consumed, reservation.released, reservation.revision, reservation.returned):
        if value > MAX_INT:
            raise InvalidQuantityError()
    balance.on_hand, balance.reserved, balance.revision = after.on_hand, after.reserved, after.revision
    balance.save(update_fields=['on_hand', 'reserved', 'revision'])
    line.remaining_reserved, line.consumed, line.released = (
        reservation.remaining_reserved, reservation.consumed, reservation.released)
    line.state, line.expires_at, line.revision = reservation.state.value, reservation.expires_at, reservation.revision
    line.returned = reservation.returned
    line.save(force_insert=line._state.adding)
    payload = dict(kind=kind.value, variant_id=balance.variant_id, location_id=balance.location_id,
        quantity=quantity, expected_revision=context.expected_revision, reason=context.reason,
        reservation_id=reservation.reservation_id,
        expected_reservation_revision=before_line.revision if before_line is not None else 0)
    if kind.value == 'checked_return':
        payload.update(received=True, inspected=True)
    payload_fingerprint = fingerprint(dict(payload, expires_at=(
        reservation.expires_at.isoformat() if kind.value == 'reserve' and reservation.expires_at else None)))
    movement = InventoryMovement.objects.create(source=context.source, owner=context.owner,
        operation_key=context.operation_key, **payload, fingerprint=payload_fingerprint,
        actor=actor, before_on_hand=before_stock.on_hand, before_reserved=before_stock.reserved,
        after_on_hand=after.on_hand, after_reserved=after.reserved,
        delta_on_hand=after.on_hand - before_stock.on_hand,
        delta_reserved=after.reserved - before_stock.reserved, revision=after.revision,
        before_reservation=encode_reservation(before_line), after_reservation=encode_reservation(reservation), decision_at=now)
    StaffAuditEvent.objects.create(actor=actor, action=f'inventory.{kind.value}',
        object_type=movement._meta.label_lower, object_id=str(movement.pk))
    return result
