from .inventory_error import InventoryError


class StockNotConfiguredError(InventoryError):
    code = "stock_not_configured"
    action = "configure_stock"
