from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from web.cart.session_cart import quote
from web.catalog.recommendations import collection_suggestions
from web.storefront.page_view import StorefrontPageView


@method_decorator(never_cache, name="dispatch")
class CartPageView(StorefrontPageView):
    template_name = "cart/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cart"] = quote(self.request)
        context["collection_suggestions"] = collection_suggestions(
            excluded_skus=tuple(line["sku"] for line in context["cart"]["lines"]),
        )
        self.cart_context = context["cart"]
        return context

    def get_template_names(self):
        return ["cart/detail.html" if self.cart_context["lines"] else "cart/empty.html"]
