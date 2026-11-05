import re
from dataclasses import dataclass

from codex_ecommerce.inventory import InvalidQuantityError, InventoryInvariantError

from .operation_store import MAX_INT


@dataclass(frozen=True, slots=True)
class FakeSourceFact:
    """Synthetic test command only; no eBay credentials, customer or listing names."""

    external_id: str
    variant_id: int
    kind: str
    quantity: int
    source_revision: int
    expected_stock_revision: int | None = None

    def __post_init__(self):
        if (not isinstance(self.external_id, str)
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}', self.external_id)
                or type(self.variant_id) is not int or not 0 < self.variant_id <= MAX_INT
                or self.kind not in ('snapshot', 'completed_sale')
                or type(self.source_revision) is not int or not 0 < self.source_revision <= MAX_INT):
            raise InventoryInvariantError()
        if (type(self.quantity) is not int or not 0 <= self.quantity <= MAX_INT
                or (self.kind == 'completed_sale' and self.quantity == 0)):
            raise InvalidQuantityError()
        if self.kind == 'snapshot':
            if type(self.expected_stock_revision) is not int or not 1 <= self.expected_stock_revision < MAX_INT:
                raise InventoryInvariantError()
        elif self.expected_stock_revision is not None:
            raise InventoryInvariantError()
