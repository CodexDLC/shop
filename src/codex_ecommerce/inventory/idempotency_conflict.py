from .inventory_error import InventoryError


class IdempotencyConflictError(InventoryError):
    code = "idempotency_conflict"
    action = "review_operation"
