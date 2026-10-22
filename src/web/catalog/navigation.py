"""Publication-aware navigation without loading product collections."""

from django.db.models import Exists, OuterRef
from django.utils import timezone

from .category_visibility import visible_category_ids
from .models import Product, ProductVariant


def header_section_visibility():
    variants = ProductVariant.objects.filter(
        product_id=OuterRef("pk"), is_active=True, currency="EUR",
    )
    published = Product.objects.filter(is_active=True, category_id__in=visible_category_ids()).filter(Exists(variants))
    checks = {
        "new": Exists(published.filter(new_until__gte=timezone.localdate())),
        "underwear": Exists(published.filter(category__section="underwear")),
        "swimwear": Exists(published.filter(category__section="swimwear")),
        "brands": Exists(published),
        "sale": Exists(published.filter(Exists(variants.filter(is_on_sale=True)))),
    }
    # Any product can anchor the single SELECT; all checks are global EXISTS.
    row = Product.objects.order_by("pk").annotate(**checks).values(*checks).first()
    return row or dict.fromkeys(checks, False)
