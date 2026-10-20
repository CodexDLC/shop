from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef
from django.http import QueryDict
from django.urls import reverse

from web.storefront.page_view import StorefrontPageView

from .listing_request import ListingRequest
from .models import Brand, Product, ProductVariant


class BrandDirectoryView(StorefrontPageView):
    """One paginated brand directory; global navigation performs no brand queries."""

    template_name = "catalog/brands.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_variant = ProductVariant.objects.filter(
            product_id=OuterRef("pk"), is_active=True, currency="EUR",
        )
        visible_product = Product.objects.filter(
            brand_id=OuterRef("pk"), is_active=True,
        ).filter(Exists(active_variant))
        brands = Brand.objects.filter(Exists(visible_product)).order_by("name", "pk")
        paginator = Paginator(brands, 24)
        page = paginator.get_page(ListingRequest.from_query(self.request.GET).page)
        context["brand_links"] = []
        for brand in page.object_list:
            params = QueryDict(mutable=True)
            params["brand"] = brand.slug
            context["brand_links"].append({
                "name": brand.name, "url": reverse("catalog:list") + "?" + params.urlencode(),
            })
        action = reverse("catalog:brands")

        def page_url(number):
            return action + (f"?page={number}" if number != 1 else "")

        numbers = sorted({1, paginator.num_pages, *range(max(1, page.number - 2),
                                                       min(paginator.num_pages, page.number + 2) + 1)})
        context.update(
            brand_page=page,
            previous_url=page_url(page.previous_page_number()) if page.has_previous() else "",
            next_url=page_url(page.next_page_number()) if page.has_next() else "",
            page_links=[{"number": number, "url": page_url(number), "current": number == page.number}
                        for number in numbers],
        )
        return context
