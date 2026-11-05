from .invalid_quantity import InvalidQuantityError
from .inventory_invariant import InventoryInvariantError
from .operation_context import OperationContext
from .stale_revision import StaleRevisionError
from .stock_key import StockKey
from .stock_rules import require_stock
from .stock_snapshot import StockSnapshot
from .validation import nonnegative_int


def _context(context, revision):
    if not isinstance(context, OperationContext):
        raise InventoryInvariantError()
    if context.expected_revision != revision:
        raise StaleRevisionError()


def initialize_stock(key: StockKey, quantity: int, context: OperationContext) -> StockSnapshot:
    """Calculate explicit initialization; adapter must guarantee absence."""
    nonnegative_int(quantity)
    _context(context, 0)
    return StockSnapshot(key, quantity, 0, 1)


def receive_stock(stock: StockSnapshot | None, quantity: int, context: OperationContext) -> StockSnapshot:
    nonnegative_int(quantity)
    if quantity == 0:
        raise InvalidQuantityError()
    stock = require_stock(stock)
    _context(context, stock.revision)
    return StockSnapshot(stock.key, stock.on_hand + quantity, stock.reserved, stock.revision + 1)


def adjust_stock(stock: StockSnapshot | None, quantity: int, context: OperationContext) -> StockSnapshot:
    nonnegative_int(quantity)
    stock = require_stock(stock)
    _context(context, stock.revision)
    return StockSnapshot(stock.key, quantity, stock.reserved, stock.revision + 1)
