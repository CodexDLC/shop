from dataclasses import dataclass

from codex_ecommerce.inventory import StockSnapshot


@dataclass(frozen=True, slots=True)
class FakeSourceResult:
    receipt_id: int
    external_id: str
    status: str
    code: str
    stock: StockSnapshot | None
    reservation_id: str | None = None
