from codex_django.cabinet import StaffRequiredMixin
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404

from web.catalog.adapters import CatalogVariantSelection
from web.catalog.models import Product, ProductVariant
from web.catalog.variant_preview_view import VariantPreviewView
from web.inventory.availability_queries import with_availability


class ProductVariantPreviewView(PermissionRequiredMixin, StaffRequiredMixin, VariantPreviewView):
    permission_required = 'catalog.view_product'

    def get(self, request, pk):
        self.product = get_object_or_404(Product.objects.prefetch_related(
            Prefetch('variants', queryset=with_availability(ProductVariant.objects.all())), 'images'), pk=pk)
        response = super().get(request, self.product.slug)
        response['Cache-Control'] = 'private, no-store'
        return response

    def select(self, slug, color, size):
        return CatalogVariantSelection().select_snapshot(self.product, color=color, size=size)
