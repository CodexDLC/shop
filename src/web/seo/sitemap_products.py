from django.db.models import Exists, OuterRef
from django.utils import timezone

from web.catalog.category_visibility import visible_category_ids
from web.catalog.models import Product, ProductVariant


def product_is_published(product):
    """Use the prefetched detail snapshot, with the same gate as the sitemap."""
    return bool(product.is_active and product.published_at and product.published_at <= timezone.now()
                and product.description_key != 'catalog.product.demo_description'
                and all(tag.slug != 'demo' for tag in product.tags.all())
                and not any(row.sku.startswith('DEMO-') for row in product.variants.all())
                and any(row.is_active and row.currency == 'EUR' for row in product.variants.all()))


def sitemap_products():
    """Publication is explicit; known seed markers never count as real data."""
    active_variant = ProductVariant.objects.filter(product_id=OuterRef('pk'), is_active=True, currency='EUR')
    demo_variant = ProductVariant.objects.filter(product_id=OuterRef('pk'), is_active=True, sku__startswith='DEMO-')
    demo_tag = Product.tags.through.objects.filter(product_id=OuterRef('pk'), tag__slug='demo')
    return (Product.objects.filter(is_active=True, category_id__in=visible_category_ids(), published_at__isnull=False, published_at__lte=timezone.now())
            .filter(Exists(active_variant)).filter(~Exists(demo_variant), ~Exists(demo_tag))
            .exclude(description_key='catalog.product.demo_description').order_by('pk').values_list('slug', flat=True))
