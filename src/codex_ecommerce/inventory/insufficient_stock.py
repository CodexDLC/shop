from .inventory_error import InventoryError


class InsufficientStockError(InventoryError):
    code = "insufficient_stock"
    action = "reduce_quantity"
