from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Count, Exists, Max, Min, OuterRef, Q, Sum

from web.catalog.models import Brand, Category, Product, ProductVariant
from web.staff.views.staff_page_view import StaffPageView


class ProductListView(PermissionRequiredMixin, StaffPageView):
    permission_required = "catalog.view_product"
    template_name = "staff/products.html"
    cabinet_space = "staff"
    cabinet_module = "catalog"
    http_method_names = ["get", "head", "options"]
    page_size = 24

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "").strip()[:200]
        brand = self.request.GET.get("brand", "").strip()[:120]
        category = self.request.GET.get("category", "").strip()[:120]
        active = Q(variants__is_active=True)
        products = Product.objects.select_related("brand", "category").annotate(
            variant_count=Count("variants"),
            active_variant_count=Count("variants", filter=active),
            available_quantity=Sum("variants__demo_quantity", filter=active, default=0),
            minimum_price=Min("variants__price", filter=active),
            maximum_price=Max("variants__price", filter=active),
            price_currency=Min("variants__currency", filter=active),
            currency_count=Count("variants__currency", filter=active, distinct=True),
        )
        if query:
            matching_sku = ProductVariant.objects.filter(product_id=OuterRef("pk"), sku__icontains=query)
            products = products.filter(
                Q(model_name__icontains=query) | Q(brand__name__icontains=query) | Exists(matching_sku)
            )
        if brand:
            products = products.filter(brand__slug=brand)
        if category:
            products = products.filter(category__slug=category)
        page = Paginator(products.order_by("pk"), self.page_size).get_page(self.request.GET.get("page"))
        parameters = self.request.GET.copy()
        parameters.pop("page", None)
        parameters["q"] = query
        parameters["brand"] = brand
        parameters["category"] = category
        context.update(
            products=page.object_list,
            page_obj=page,
            search_query=query,
            selected_brand=brand,
            selected_category=category,
            brands=Brand.objects.order_by("name", "pk"),
            categories=Category.objects.order_by("slug", "pk"),
            page_query=parameters.urlencode(),
        )
        return context
