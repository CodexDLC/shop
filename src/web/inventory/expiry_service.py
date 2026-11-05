"""Bounded cleanup with independently committed per-line expiry operations.

Internal maintenance scope cannot be supplied through staff command contexts.
PostgreSQL NOWAIT prevents a busy target from exceeding the batch time budget;
55P03 skips it for a later run. All other unknown errors propagate.
"""
from datetime import UTC
from time import monotonic

from django.db import IntegrityError, OperationalError, connection, transaction

from codex_ecommerce.inventory import (
    InventoryInvariantError,
    OperationContext,
    expire_reservation,
)
from codex_ecommerce.inventory.validation import aware_datetime
from web.catalog.models import ProductVariant
from web.staff.models import StaffAuditEvent

from .access import require_actor
from .expiry_backlog_error import ExpiryBacklogError
from .expiry_summary import ExpirySummary
from .expiry_transaction_error import ExpiryTransactionError
from .models import InventoryMovement, ReservationLine, StockBalance
from .operation_store import MAX_INT, fingerprint, unique_constraint
from .snapshots import balance_snapshot, encode_reservation, reservation_snapshot
from .write_access import service_write

BATCH_TIME_LIMIT = 5.0
SKU_BATCH_SIZE = 20


def _validate(now, batch_size):
    aware_datetime(now)
    if type(batch_size) is not int or not 1 <= batch_size <= 100:
        raise InventoryInvariantError()
    return now.astimezone(UTC)


def _due(now, variant_id=None, exclude_reference=None):
    query = ReservationLine.objects.filter(state='held', expires_at__lte=now)
    if variant_id is not None:
        query = query.filter(variant_id=variant_id, location_id='main')
    if exclude_reference is not None:
        query = query.exclude(reference=exclude_reference)
    return query.order_by('expires_at', 'variant_id', 'reference')


def _require_autocommit():
    if connection.in_atomic_block or not connection.get_autocommit():
        raise ExpiryTransactionError()


def _expire_one(*, actor, variant_id, reference, now):
    for attempt in range(2):
        try:
            with transaction.atomic(), service_write():
                variant = ProductVariant.objects.select_for_update(nowait=True).filter(pk=variant_id).first()
                balance = StockBalance.objects.select_for_update(nowait=True).filter(
                    variant_id=variant_id, location_id='main').first()
                line = ReservationLine.objects.select_for_update(nowait=True).filter(
                    reference=reference, variant_id=variant_id, location_id='main').first()
                if line is None or line.state != 'held' or line.expires_at > now:
                    return False
                if variant is None or balance is None:
                    raise InventoryInvariantError()
                before_stock, before_line = balance_snapshot(balance), reservation_snapshot(line)
                if before_stock.revision >= MAX_INT or before_line.revision >= MAX_INT:
                    raise InventoryInvariantError()
                context = OperationContext(f'expire:{reference}', 'inventory_expiry', 'system',
                    'Reservation deadline reached', before_stock.revision)
                result = expire_reservation(before_stock, before_line, context,
                    expected_reservation_revision=before_line.revision, now=now)
                after, reservation = result.stock, result.reservation
                balance.reserved, balance.revision = after.reserved, after.revision
                balance.save(update_fields=['reserved', 'revision'])
                line.remaining_reserved, line.released = reservation.remaining_reserved, reservation.released
                line.state, line.expires_at, line.revision = reservation.state.value, None, reservation.revision
                line.save(update_fields=['remaining_reserved', 'released', 'state', 'expires_at', 'revision'])
                payload = dict(kind='expire', variant_id=variant_id, location_id='main', quantity=before_line.remaining_reserved,
                    expected_revision=context.expected_revision, reason=context.reason,
                    reservation_id=reference, expected_reservation_revision=before_line.revision)
                movement = InventoryMovement.objects.create(source=context.source, owner=context.owner,
                    operation_key=context.operation_key, **payload, fingerprint=fingerprint(payload), actor=actor,
                    before_on_hand=before_stock.on_hand, before_reserved=before_stock.reserved,
                    after_on_hand=after.on_hand, after_reserved=after.reserved, delta_on_hand=0,
                    delta_reserved=-before_line.remaining_reserved, revision=after.revision,
                    before_reservation=encode_reservation(before_line), after_reservation=encode_reservation(reservation),
                    decision_at=now)
                StaffAuditEvent.objects.create(actor=actor, action='inventory.expire',
                    object_type=movement._meta.label_lower, object_id=str(movement.pk))
                return True
        except IntegrityError as error:
            if unique_constraint(error) != 'inventory_unique_operation':
                raise
            # A canonical key on a still-open line is corruption, not a reason
            # to suppress the failure and leave unaccounted reserved stock.
            if ReservationLine.objects.filter(reference=reference, state='closed').exists():
                return False
            raise
        except OperationalError as error:
            code = getattr(error.__cause__, 'sqlstate', None)
            if code == '55P03':
                return False
            if attempt != 0 or code not in {'40001', '40P01'}:
                raise
    raise AssertionError('Unreachable expiry attempt state')


def _run(*, actor, now, batch_size, variant_id=None, exclude_reference=None):
    deadline = monotonic() + BATCH_TIME_LIMIT
    query = _due(now, variant_id, exclude_reference)
    candidates = list(query.values_list('variant_id', 'reference')[:batch_size])
    scanned = expired = 0
    for target_id, reference in candidates:
        if monotonic() >= deadline:
            break
        scanned += 1
        expired += int(_expire_one(actor=actor, variant_id=target_id, reference=reference, now=now))
    return ExpirySummary(scanned, expired, scanned - expired, query.exists())


def expire_due_reservations(*, actor, now, batch_size=100):
    actor = require_actor(actor, 'expire_reservationline')
    now = _validate(now, batch_size)
    _require_autocommit()
    return _run(actor=actor, now=now, batch_size=batch_size)


def due_reservations(*, actor, now, batch_size=100):
    require_actor(actor, 'expire_reservationline')
    now = _validate(now, batch_size)
    candidates = list(_due(now).values_list('reference', flat=True)[:batch_size + 1])
    count = min(len(candidates), batch_size)
    return ExpirySummary(count, 0, count, len(candidates) > batch_size)


def opportunistic_cleanup(*, actor, variant_id, now, exclude_reference=None):
    """Internal maintenance after main action authorization and replay lookup."""
    now = _validate(now, SKU_BATCH_SIZE)
    if not _due(now, variant_id, exclude_reference).exists():
        return
    _require_autocommit()
    summary = _run(actor=actor, now=now, batch_size=SKU_BATCH_SIZE, variant_id=variant_id,
        exclude_reference=exclude_reference)
    if summary.has_more:
        raise ExpiryBacklogError()


def require_no_due_locked(*, variant_id, now, exclude_reference=None):
    """Do not mutate if new due work appeared after the pre-transaction scan."""
    if _due(now, variant_id, exclude_reference).exists():
        raise ExpiryBacklogError()
