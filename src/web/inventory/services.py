"""Local staff accounting. Lock order: variant, balance; one target per command.

No network work occurs in the transaction. A scoped-key collision on another
target rolls back the entire losing transaction before its original result is
read. Only named inventory unique constraints are recovered, never arbitrary
IntegrityError. PostgreSQL aborted serialization/deadlock transactions receive
at most one complete retry; business errors are never retried.
"""
from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone

from codex_ecommerce.inventory import (
    InvalidQuantityError,
    InvalidTransitionError,
    InventoryInvariantError,
    OperationKind,
    StockKey,
    adjust_stock,
    initialize_stock,
    receive_stock,
)
from web.catalog.models import ProductVariant
from web.staff.models import StaffAuditEvent

from .access import require_actor
from .expiry_service import opportunistic_cleanup, require_no_due_locked
from .models import InventoryMovement, StockBalance
from .operation_store import MAX_INT as _MAX_INT
from .operation_store import fingerprint as payload_fingerprint
from .operation_store import replay as _replay
from .operation_store import trusted_context
from .operation_store import unique_constraint as _unique_constraint
from .reservation_services import checked_return, commit, fulfill, release, reserve
from .snapshots import balance_snapshot
from .write_access import service_write

__all__ = ['initialize', 'receive', 'adjust', 'reserve', 'commit', 'release', 'fulfill', 'checked_return']


def _execute(*, actor, variant_id, quantity, context, kind, location_id, now):
    actor = require_actor(actor, f'{kind.value}_stockbalance')
    context = trusted_context(actor, context)
    if location_id != 'main' or type(variant_id) is not int or variant_id <= 0:
        raise InventoryInvariantError()
    if type(quantity) is not int or not 0 <= quantity <= _MAX_INT:
        raise InvalidQuantityError()
    scope = dict(source='staff', owner=str(actor.pk), operation_key=context.operation_key)
    payload = dict(kind=kind.value, variant_id=variant_id, location_id=location_id,
        quantity=quantity, expected_revision=context.expected_revision, reason=context.reason)
    fingerprint = payload_fingerprint(payload)
    result = _replay(scope, fingerprint)
    if result is not None:
        return result
    now = timezone.now() if now is None else now
    opportunistic_cleanup(actor=actor, variant_id=variant_id, now=now)
    for attempt in range(2):
        try:
            with transaction.atomic(), service_write():
                # Locking the parent also serializes first balance creation, for
                # which there is no balance row to lock yet.
                variant = ProductVariant.objects.select_for_update().filter(pk=variant_id).first()
                balance = StockBalance.objects.select_for_update().filter(
                    variant_id=variant_id, location_id=location_id).first()
                result = _replay(scope, fingerprint)
                if result is not None:
                    return result
                require_no_due_locked(variant_id=variant_id, now=now)
                if variant is None or not variant.is_active:
                    raise InventoryInvariantError()
                before = balance_snapshot(balance)
                if kind is OperationKind.INITIALIZE:
                    if balance is not None:
                        raise InvalidTransitionError()
                    after = initialize_stock(StockKey(str(variant_id), location_id), quantity, context)
                    balance = StockBalance(variant_id=variant_id, location_id=location_id,
                        on_hand=after.on_hand, reserved=after.reserved, revision=after.revision)
                else:
                    calculation = receive_stock if kind is OperationKind.RECEIVE else adjust_stock
                    after = calculation(before, quantity, context)
                    if after.on_hand > _MAX_INT:
                        raise InvalidQuantityError()
                    balance.on_hand, balance.reserved, balance.revision = after.on_hand, after.reserved, after.revision
                balance.save()
                movement = InventoryMovement.objects.create(**scope, **payload, fingerprint=fingerprint,
                    actor=actor, before_on_hand=before.on_hand if before else 0,
                    before_reserved=before.reserved if before else 0,
                    after_on_hand=after.on_hand, after_reserved=after.reserved,
                    delta_on_hand=after.on_hand - (before.on_hand if before else 0),
                    delta_reserved=after.reserved - (before.reserved if before else 0), revision=after.revision)
                StaffAuditEvent.objects.create(actor=actor, action=f'inventory.{kind.value}',
                    object_type=movement._meta.label_lower, object_id=str(movement.pk))
                return after
        except IntegrityError as error:
            if _unique_constraint(error) not in {'inventory_unique_operation', 'inventory_unique_balance'}:
                raise
            result = _replay(scope, fingerprint)
            if result is not None:
                return result
            if _unique_constraint(error) == 'inventory_unique_balance' and kind is OperationKind.INITIALIZE:
                raise InvalidTransitionError() from error
            raise
        except OperationalError as error:
            code = getattr(error.__cause__, 'sqlstate', None)
            if attempt != 0 or code not in {'40001', '40P01'}:
                raise
    raise AssertionError('Unreachable inventory attempt state')


def initialize(*, actor, variant_id, quantity, context, location_id='main', now=None):
    return _execute(actor=actor, variant_id=variant_id, quantity=quantity,
        context=context, kind=OperationKind.INITIALIZE, location_id=location_id, now=now)


def receive(*, actor, variant_id, quantity, context, location_id='main', now=None):
    return _execute(actor=actor, variant_id=variant_id, quantity=quantity,
        context=context, kind=OperationKind.RECEIVE, location_id=location_id, now=now)


def adjust(*, actor, variant_id, quantity, context, location_id='main', now=None):
    return _execute(actor=actor, variant_id=variant_id, quantity=quantity,
        context=context, kind=OperationKind.ADJUST, location_id=location_id, now=now)
