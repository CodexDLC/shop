from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from web.storefront.page_view import StorefrontPageView

from .selectors import wishlist_products


@method_decorator(never_cache, name="dispatch")
class WishlistDetailView(StorefrontPageView):
    template_name = "wishlist/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["wishlist_products"] = wishlist_products(self.request)
        return context
