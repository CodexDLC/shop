from web.localization import translate_text
from web.localization.translation import source_messages
from web.storefront.page_view import StorefrontPageView
from web.storefront.pages import page_manifest

from .listing_context import ListingContext
from .listing_request import ListingRequest
from .presentation import selection_texts


class CatalogPageView(StorefrontPageView):
    """All catalog/search routes expose one read-only, database-backed listing."""

    def get_template_names(self):
        return ["catalog/list.html"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        listing = ListingContext(ListingRequest.from_query(self.request.GET)).build()
        context["catalog_listing"] = listing
        filters = listing["filters"]
        if len(filters.get("category", [])) == 1:
            from .category_visibility import visible_category_ids
            from .models import Category

            context["selected_category"] = Category.objects.filter(
                slug=filters["category"][0], pk__in=visible_category_ids()).first()
        heading = "new" if filters.get("new") else "sale" if filters.get("sale") else filters.get("section")
        context["catalog_heading_key"] = f"catalog.heading.{heading}" if heading else ""
        context["catalog_products"] = listing["products"]
        context["products"] = {product["code"]: product for product in listing["products"]}
        context["catalog_selection_texts"] = selection_texts()
        context["listing_page"] = True
        context["catalog_source"] = next(
            (page["source"] for page in page_manifest() if page.get("template") == self.template_name),
            "catalog.html",
        )
        context["shop_texts"].update({key: translate_text(key) for key in source_messages()
                                     if key.startswith("catalog.")})
        return context
