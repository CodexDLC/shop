from dataclasses import dataclass

from .inventory_invariant import InventoryInvariantError
from .reservation_snapshot import ReservationSnapshot
from .stock_snapshot import StockSnapshot


@dataclass(frozen=True, slots=True)
class ReservationResult:
    stock: StockSnapshot
    reservation: ReservationSnapshot

    def __post_init__(self):
        if not isinstance(self.stock, StockSnapshot) or not isinstance(self.reservation, ReservationSnapshot):
            raise InventoryInvariantError()
        if self.stock.key != self.reservation.key or self.stock.reserved < self.reservation.remaining_reserved:
            raise InventoryInvariantError()
