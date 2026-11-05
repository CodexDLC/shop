"""Immutable read snapshot. Positive availability never guarantees a reservation."""
from dataclasses import dataclass

from .checkout_policy import stock_mode


@dataclass(frozen=True, slots=True)
class InventoryAvailability:
    mode: str
    quantity: int | None
    eligible: bool

    @property
    def configured(self):
        return self.quantity is not None

    @property
    def available(self):
        return self.eligible and self.configured and self.quantity > 0

    @classmethod
    def from_variant(cls, variant, *, balances=None):
        mode = stock_mode()
        if mode == 'demo':
            quantity = variant.demo_quantity
        elif balances is not None:
            # Final checkout supplies already locked rows; never reread them here.
            balance = balances.get(variant.pk)
            quantity = balance.on_hand - balance.reserved if balance is not None else None
        else:
            if getattr(variant, 'availability_mode', None) != mode:
                raise ValueError('Inventory availability requires a fresh with_availability queryset.')
            quantity = variant.availability_quantity
        return cls(mode, quantity, variant.is_active and variant.currency == 'EUR')
