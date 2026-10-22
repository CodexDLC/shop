from codex_django.cabinet import StaffRequiredMixin
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.cache import patch_cache_control

from web.catalog.models import Product
from web.catalog.product_detail_view import ProductDetailView


class ProductPreviewView(PermissionRequiredMixin, StaffRequiredMixin, ProductDetailView):
    permission_required = 'catalog.view_product'
    http_method_names = ['get', 'head', 'options']

    def get_product(self):
        return get_object_or_404(Product.objects.select_related('brand', 'category').prefetch_related(
            'variants', 'images', 'tags',
        ), pk=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['staff_product_preview'] = True
        context['staff_product_pk'] = self.kwargs['pk']
        context['seo_product_published'] = False
        context['product']['preview_url'] = reverse('staff:product_variant_preview', kwargs=self.kwargs)
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        patch_cache_control(response, private=True, no_store=True, no_cache=True)
        response['X-Robots-Tag'] = 'noindex, nofollow'
        return response
