"""Staff reservation commands; locks follow variant -> balance -> reservation.

The same dedup namespace as accounting applies. now is a decision observation,
not a business-payload version: an authorized successful retry returns the
stored original result even at a later time. Failed decisions claim no key.
"""
from datetime import UTC

from django.db import IntegrityError, OperationalError, transaction

from codex_ecommerce.inventory import (
    InvalidQuantityError,
    InvalidTransitionError,
    InventoryInvariantError,
    OperationKind,
    ReservationExpiredError,
    StaleRevisionError,
    checked_return_reservation,
    commit_reservation,
    fulfill_reservation,
    release_reservation,
    reserve_stock,
)
from codex_ecommerce.inventory.validation import aware_datetime
from web.catalog.models import ProductVariant

from .access import require_actor
from .expiry_service import opportunistic_cleanup, require_no_due_locked
from .models import InventoryMovement, ReservationLine, StockBalance
from .operation_store import MAX_INT, fingerprint, replay, trusted_context, unique_constraint
from .references import require_reference
from .reservation_persistence import persist_reservation_result
from .snapshots import balance_snapshot, reservation_snapshot
from .write_access import service_write


def _execute(*, actor, variant_id, reservation_id, quantity, context, kind,
        expected_reservation_revision, now, expires_at, location_id, received=None, inspected=None):
    actor = require_actor(actor, f'{kind.value}_reservationline')
    if kind is OperationKind.CHECKED_RETURN and (received is not True or inspected is not True):
        raise InvalidTransitionError()
    context = trusted_context(actor, context)
    require_reference(reservation_id)
    if location_id != 'main' or type(variant_id) is not int or variant_id <= 0:
        raise InventoryInvariantError()
    if type(quantity) is not int or not 0 <= quantity <= MAX_INT:
        raise InvalidQuantityError()
    if type(expected_reservation_revision) is not int or not 0 <= expected_reservation_revision < MAX_INT:
        raise InvalidQuantityError()
    aware_datetime(now)
    now = now.astimezone(UTC)
    if kind is OperationKind.RESERVE:
        aware_datetime(expires_at)
        expires_at = expires_at.astimezone(UTC)
    scope = dict(source='staff', owner=str(actor.pk), operation_key=context.operation_key)
    payload = dict(kind=kind.value, variant_id=variant_id, location_id=location_id,
        quantity=quantity, expected_revision=context.expected_revision, reason=context.reason,
        reservation_id=reservation_id, expected_reservation_revision=expected_reservation_revision)
    if kind is OperationKind.CHECKED_RETURN:
        payload.update(received=True, inspected=True)
    payload_fingerprint = fingerprint(dict(payload, expires_at=expires_at.isoformat() if expires_at else None))
    result = replay(scope, payload_fingerprint)
    if result is not None:
        return result
    exclude_reference = reservation_id if kind is OperationKind.RELEASE else None
    opportunistic_cleanup(actor=actor, variant_id=variant_id, now=now, exclude_reference=exclude_reference)
    if kind is OperationKind.COMMIT and InventoryMovement.objects.filter(kind='expire',
            source='inventory_expiry', owner='system', reservation_id=reservation_id,
            variant_id=variant_id, location_id=location_id).exists():
        raise ReservationExpiredError()
    for attempt in range(2):
        try:
            with transaction.atomic(), service_write():
                variant = ProductVariant.objects.select_for_update().filter(pk=variant_id).first()
                balance = StockBalance.objects.select_for_update().filter(
                    variant_id=variant_id, location_id=location_id).first()
                # Never lock a reservation belonging to another target while
                # holding this target's parent/balance locks.
                line = ReservationLine.objects.select_for_update().filter(reference=reservation_id,
                    variant_id=variant_id, location_id=location_id).first()
                result = replay(scope, payload_fingerprint)
                if result is not None:
                    return result
                require_no_due_locked(variant_id=variant_id, now=now, exclude_reference=exclude_reference)
                if (kind is OperationKind.COMMIT and line is not None and line.state == 'closed'
                        and InventoryMovement.objects.filter(kind='expire', source='inventory_expiry',
                            owner='system', reservation_id=reservation_id).exists()):
                    raise ReservationExpiredError()
                if variant is None:
                    raise InventoryInvariantError()
                before_stock = balance_snapshot(balance)
                before_line = reservation_snapshot(line)
                if kind is OperationKind.RESERVE:
                    if not variant.is_active:
                        raise InventoryInvariantError()
                    if line is not None or ReservationLine.objects.filter(reference=reservation_id).exists():
                        raise InvalidTransitionError()
                    if expected_reservation_revision != 0:
                        raise StaleRevisionError()
                    result = reserve_stock(before_stock, reservation_id, quantity, context, expires_at=expires_at, now=now)
                    line = ReservationLine(reference=reservation_id, variant_id=variant_id,
                        location_id=location_id, original=result.reservation.original)
                else:
                    if line is None or line.variant_id != variant_id or line.location_id != location_id:
                        raise InventoryInvariantError()
                    args = dict(expected_reservation_revision=expected_reservation_revision, now=now)
                    if kind is OperationKind.COMMIT:
                        result = commit_reservation(before_stock, before_line, context, **args)
                    elif kind is OperationKind.CHECKED_RETURN:
                        result = checked_return_reservation(before_stock, before_line, quantity, context,
                            received=received, inspected=inspected, **args)
                    else:
                        calculation = release_reservation if kind is OperationKind.RELEASE else fulfill_reservation
                        result = calculation(before_stock, before_line, quantity, context, **args)
                return persist_reservation_result(actor=actor, kind=kind, context=context, balance=balance,
                    line=line, result=result, before_stock=before_stock, before_line=before_line,
                    quantity=quantity, now=now)
        except IntegrityError as error:
            constraint = unique_constraint(error)
            if constraint not in {'inventory_unique_operation', 'inventory_reservationline_pkey'}:
                raise
            result = replay(scope, payload_fingerprint)
            if result is not None:
                return result
            if constraint == 'inventory_reservationline_pkey' and kind is OperationKind.RESERVE:
                raise InvalidTransitionError() from error
            raise
        except OperationalError as error:
            if attempt != 0 or getattr(error.__cause__, 'sqlstate', None) not in {'40001', '40P01'}:
                raise
    raise AssertionError('Unreachable reservation attempt state')


def reserve(*, actor, variant_id, reservation_id, quantity, context, expires_at, now,
        expected_reservation_revision=0, location_id='main'):
    return _execute(actor=actor, variant_id=variant_id, reservation_id=reservation_id, quantity=quantity,
        context=context, kind=OperationKind.RESERVE, expected_reservation_revision=expected_reservation_revision,
        now=now, expires_at=expires_at, location_id=location_id)


def commit(*, actor, variant_id, reservation_id, context, expected_reservation_revision, now, location_id='main'):
    return _execute(actor=actor, variant_id=variant_id, reservation_id=reservation_id, quantity=0,
        context=context, kind=OperationKind.COMMIT, expected_reservation_revision=expected_reservation_revision,
        now=now, expires_at=None, location_id=location_id)


def release(*, actor, variant_id, reservation_id, quantity, context, expected_reservation_revision, now, location_id='main'):
    return _execute(actor=actor, variant_id=variant_id, reservation_id=reservation_id, quantity=quantity,
        context=context, kind=OperationKind.RELEASE, expected_reservation_revision=expected_reservation_revision,
        now=now, expires_at=None, location_id=location_id)


def fulfill(*, actor, variant_id, reservation_id, quantity, context, expected_reservation_revision, now, location_id='main'):
    return _execute(actor=actor, variant_id=variant_id, reservation_id=reservation_id, quantity=quantity,
        context=context, kind=OperationKind.FULFILL, expected_reservation_revision=expected_reservation_revision,
        now=now, expires_at=None, location_id=location_id)


def checked_return(*, actor, variant_id, reservation_id, quantity, context,
        expected_reservation_revision, now, received, inspected, location_id='main'):
    # Both accepted attestations are exactly True, including replay. There is
    # no alternate successful payload: false/non-bool input never claims a key.
    return _execute(actor=actor, variant_id=variant_id, reservation_id=reservation_id, quantity=quantity,
        context=context, kind=OperationKind.CHECKED_RETURN, expected_reservation_revision=expected_reservation_revision,
        now=now, expires_at=None, location_id=location_id, received=received, inspected=inspected)
