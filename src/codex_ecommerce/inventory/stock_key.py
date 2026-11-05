from dataclasses import dataclass

from .validation import identifier


@dataclass(frozen=True, slots=True)
class StockKey:
    variant_id: str
    location_id: str

    def __post_init__(self):
        identifier(self.variant_id)
        identifier(self.location_id)
