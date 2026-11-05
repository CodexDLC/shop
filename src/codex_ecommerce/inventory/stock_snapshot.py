from dataclasses import dataclass

from .inventory_invariant import InventoryInvariantError
from .stock_key import StockKey
from .validation import nonnegative_int


@dataclass(frozen=True, slots=True)
class StockSnapshot:
    """A validated snapshot, not a lock or a promise of availability."""

    key: StockKey
    on_hand: int
    reserved: int
    revision: int

    def __post_init__(self):
        if not isinstance(self.key, StockKey):
            raise InventoryInvariantError()
        for value in (self.on_hand, self.reserved, self.revision):
            nonnegative_int(value)
        if self.reserved > self.on_hand:
            raise InventoryInvariantError()

    @property
    def available(self):
        return self.on_hand - self.reserved
