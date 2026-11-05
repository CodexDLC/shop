from .inventory_error import InventoryError


class InvalidQuantityError(InventoryError):
    code = "invalid_quantity"
    action = "review_input"
