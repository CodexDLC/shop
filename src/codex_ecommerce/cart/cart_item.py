from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CartItem:
    sku: str
    quantity: int
    unit_amount: Decimal
    currency: str
    available_quantity: int
