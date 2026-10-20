from django.db.models import Exists, OuterRef

from .models import ProductVariant
from .presentation import product_presentation
from .selectors import storefront_products


def collection_suggestions(*, excluded_skus=()):
    """Three real catalog models, without claims of personalized ranking."""
    available = ProductVariant.objects.filter(product_id=OuterRef("pk"), is_active=True, currency="EUR")
    products = storefront_products().filter(Exists(available))
    if excluded_skus:
        excluded = ProductVariant.objects.filter(product_id=OuterRef("pk"), sku__in=excluded_skus)
        products = products.filter(~Exists(excluded))
    return [product_presentation(product, code=f"suggested-{product.pk}", currency="EUR")
            for product in products.order_by("pk")[:3]]
