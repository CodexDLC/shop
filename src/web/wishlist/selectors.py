from django.db.models import Exists, OuterRef

from web.catalog.models import ProductVariant
from web.catalog.presentation import product_presentation
from web.catalog.selectors import storefront_products

from .session import product_ids


def wishlist_products(request):
    ids = product_ids(request)
    if not ids:
        return []
    active_variants = ProductVariant.objects.filter(product_id=OuterRef("pk"), is_active=True, currency="EUR")
    products = storefront_products().filter(pk__in=ids).filter(Exists(active_variants)).order_by("pk")
    return [{**product_presentation(product, code=f"wishlist-{product.pk}", currency="EUR"), "id": product.pk}
            for product in products[:50]]
