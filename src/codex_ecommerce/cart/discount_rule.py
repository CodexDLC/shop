from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class DiscountRule:
    kind: str
    value: Decimal
    min_subtotal: Decimal = Decimal('0.00')
    currency: str = 'EUR'
