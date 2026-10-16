from web.catalog.presentation import product_presentation, selection_texts
from web.catalog.selectors import catalog_products
from web.storefront.page_view import StorefrontPageView


class HomeView(StorefrontPageView):
    template_name = "shop/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["products"] = {
            f"p{index}": product_presentation(product, code=f"p{index}")
            for index, product in enumerate(catalog_products(limit=4), start=1)
        }
        context["catalog_products"] = list(context["products"].values())
        context["catalog_selection_texts"] = selection_texts()
        return context
