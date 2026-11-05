from .inventory_error import InventoryError


class StaleRevisionError(InventoryError):
    code = "stale_revision"
    action = "refresh"
