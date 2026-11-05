from .inventory_error import InventoryError


class InventoryInvariantError(InventoryError):
    code = "inventory_invariant"
    action = "review_input"
