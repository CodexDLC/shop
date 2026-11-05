from .insufficient_stock import InsufficientStockError
from .invalid_quantity import InvalidQuantityError
from .inventory_invariant import InventoryInvariantError
from .stock_not_configured import StockNotConfiguredError
from .stock_snapshot import StockSnapshot


def require_stock(stock: StockSnapshot | None) -> StockSnapshot:
    """Distinguish a missing stock record from an initialized zero balance."""
    if stock is None:
        raise StockNotConfiguredError()
    if not isinstance(stock, StockSnapshot):
        raise InventoryInvariantError()
    return stock


def require_available(stock: StockSnapshot | None, quantity: int) -> StockSnapshot:
    """Validate current snapshot only; no reservation or concurrency guarantee."""
    if type(quantity) is not int or quantity <= 0:
        raise InvalidQuantityError()
    stock = require_stock(stock)
    if quantity > stock.available:
        raise InsufficientStockError()
    return stock
