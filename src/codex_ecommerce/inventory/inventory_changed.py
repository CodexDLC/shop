from dataclasses import dataclass
from datetime import UTC, datetime

from .inventory_invariant import InventoryInvariantError
from .stock_snapshot import StockSnapshot
from .validation import aware_datetime, identifier, nonnegative_int


@dataclass(frozen=True, slots=True)
class InventoryChanged:
    """Safe durable fact. Cursor is local read metadata, not delivery evidence."""

    event_id: str
    version: int
    movement_id: int
    stock: StockSnapshot
    occurred_at: datetime
    cursor: int = 0

    def __post_init__(self):
        identifier(self.event_id)
        nonnegative_int(self.movement_id)
        nonnegative_int(self.cursor)
        if type(self.version) is not int or self.version != 1 or self.movement_id == 0:
            raise InventoryInvariantError()
        if not isinstance(self.stock, StockSnapshot):
            raise InventoryInvariantError()
        aware_datetime(self.occurred_at)

    @property
    def event_type(self):
        return 'inventory_changed'

    def payload(self):
        return dict(event_id=self.event_id, event_type=self.event_type, version=self.version,
            movement_id=self.movement_id, variant_id=self.stock.key.variant_id,
            location_id=self.stock.key.location_id, revision=self.stock.revision,
            on_hand=self.stock.on_hand, reserved=self.stock.reserved, available=self.stock.available,
            occurred_at=self.occurred_at.astimezone(UTC).isoformat())
