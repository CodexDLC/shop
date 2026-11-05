import hashlib
import json
from dataclasses import replace

from django.core.exceptions import PermissionDenied

from codex_ecommerce.inventory import IdempotencyConflictError, InventoryInvariantError, OperationContext

from .models import InventoryMovement
from .snapshots import movement_snapshot

MAX_INT = 9223372036854775807


def trusted_context(actor, context):
    if not isinstance(context, OperationContext):
        raise InventoryInvariantError()
    if context.source != 'staff' or context.owner != str(actor.pk):
        raise PermissionDenied
    if (len(context.operation_key) > 160 or len(context.reason) > 500
            or context.expected_revision >= MAX_INT):
        raise InventoryInvariantError()
    return replace(context, operation_key=context.operation_key.strip(), reason=context.reason.strip())


def fingerprint(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def replay(scope, payload_fingerprint):
    movement = InventoryMovement.objects.filter(**scope).first()
    if movement is None:
        return None
    if movement.fingerprint != payload_fingerprint:
        raise IdempotencyConflictError()
    return movement_snapshot(movement)


def unique_constraint(error):
    diagnostic = getattr(error.__cause__, 'diag', None)
    return getattr(diagnostic, 'constraint_name', None)
