from django.shortcuts import get_object_or_404

from web.catalog.presentation import product_presentation, selection_texts
from web.catalog.selectors import storefront_products
from web.storefront.page_view import StorefrontPageView


class ProductDetailView(StorefrontPageView):
    template_name = "catalog/product.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = get_object_or_404(storefront_products(), slug=self.kwargs["slug"])
        context["product"] = product_presentation(product, code="pdp")
        context["products"] = {"pdp": context["product"]}
        context["catalog_selection_texts"] = selection_texts()
        return context
