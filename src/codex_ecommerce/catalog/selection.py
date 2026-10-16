from dataclasses import dataclass

from .gallery import Gallery
from .variant import Variant


@dataclass(frozen=True, slots=True)
class VariantSelection:
    variant: Variant
    gallery: Gallery

    @property
    def purchase_allowed(self) -> bool:
        """Snapshot eligibility only; checkout must revalidate and reserve stock."""
        return self.variant.active and self.variant.available
