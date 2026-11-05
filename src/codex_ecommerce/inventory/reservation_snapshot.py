from dataclasses import dataclass
from datetime import UTC, datetime

from .inventory_invariant import InventoryInvariantError
from .reservation_state import ReservationState
from .stock_key import StockKey
from .validation import aware_datetime, identifier, nonnegative_int


@dataclass(frozen=True, slots=True)
class ReservationSnapshot:
    """Immutable conserved quantities and version of one reservation line."""

    reservation_id: str
    key: StockKey
    original: int
    remaining_reserved: int
    consumed: int
    released: int
    state: ReservationState
    expires_at: datetime | None
    revision: int = 0
    returned: int = 0

    def __post_init__(self):
        identifier(self.reservation_id)
        if not isinstance(self.key, StockKey) or not isinstance(self.state, ReservationState):
            raise InventoryInvariantError()
        for value in (self.original, self.remaining_reserved, self.consumed, self.released, self.revision, self.returned):
            nonnegative_int(value)
        if self.returned > self.consumed:
            raise InventoryInvariantError()
        if not self.original:
            raise InventoryInvariantError()
        if self.original != self.remaining_reserved + self.consumed + self.released:
            raise InventoryInvariantError()
        if (self.state is ReservationState.CLOSED) != (self.remaining_reserved == 0):
            raise InventoryInvariantError()
        if self.state is ReservationState.HELD:
            if self.consumed:
                raise InventoryInvariantError()
            aware_datetime(self.expires_at)
        elif self.expires_at is not None:
            raise InventoryInvariantError()

    def is_expired(self, at: datetime) -> bool:
        """Check a snapshot at an aware instant; equality is expired."""
        aware_datetime(at)
        return (
            self.state is ReservationState.HELD
            and at.astimezone(UTC) >= self.expires_at.astimezone(UTC)
        )
