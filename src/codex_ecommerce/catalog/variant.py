"""Adapter-supplied variant snapshot, never a stock reservation."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Variant:
    sku: str
    color: str
    size: str
    price: Decimal
    currency: str
    available: bool
    active: bool = True

    def __post_init__(self):
        if not all(isinstance(value, str) and value.strip() for value in (self.sku, self.color, self.size)):
            raise ValueError("Variant identifiers must be non-empty strings")
        if not isinstance(self.price, Decimal) or not self.price.is_finite() or self.price < 0:
            raise ValueError("Variant price must be a finite non-negative Decimal")
        if not isinstance(self.currency, str) or len(self.currency) != 3 or not self.currency.isascii() \
                or not self.currency.isalpha() or self.currency != self.currency.upper():
            raise ValueError("Currency must be a three-letter uppercase code")
        if type(self.available) is not bool or type(self.active) is not bool:
            raise ValueError("Availability and activity must be explicit booleans")
