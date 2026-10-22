from django.shortcuts import get_object_or_404
from django.utils.translation import get_language

from web.catalog.presentation import product_presentation, selection_texts
from web.catalog.product_information_context import product_information_context
from web.catalog.selectors import storefront_products
from web.localization import translate_text
from web.seo.sitemap_products import product_is_published
from web.storefront.page_view import StorefrontPageView


class ProductDetailView(StorefrontPageView):
    template_name = "catalog/product.html"

    def get_product(self):
        return get_object_or_404(storefront_products(), slug=self.kwargs['slug'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.get_product()
        context['seo_product_published'] = product_is_published(product)
        context["product"] = product_presentation(product, code="pdp")
        context["products"] = {"pdp": context["product"]}
        context["catalog_selection_texts"] = selection_texts()
        context.update(product_information_context(product))
        context['manufacturer_article'] = product.manufacturer_article
        context['information_not_provided'] = translate_text('catalog.information.not_provided')
        context['information_requested_language'] = (get_language() or 'de').split('-')[0]
        return context
