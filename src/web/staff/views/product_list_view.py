from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.paginator import Paginator
from django.db.models import BigIntegerField, Count, Exists, Max, Min, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from web.catalog.models import Brand, Category, Product, ProductVariant
from web.inventory.availability_queries import with_availability
from web.inventory.checkout_policy import stock_mode
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
        state = self.request.GET.get("state", "")
        if state not in {"draft", "review", "published"}:
            state = ""
        active = Q(variants__is_active=True)
        products = Product.objects.select_related("brand", "category").annotate(
            variant_count=Count("variants"),
            active_variant_count=Count("variants", filter=active),
            minimum_price=Min("variants__price", filter=active),
            maximum_price=Max("variants__price", filter=active),
            price_currency=Min("variants__currency", filter=active),
            currency_count=Count("variants__currency", filter=active, distinct=True),
        )
        # Aggregate a single row per variant first; inventory relations must never
        # multiply product counts or cause per-product lookups.
        variants = with_availability(ProductVariant.objects.filter(product_id=OuterRef('pk'), is_active=True))
        totals = variants.order_by().values('product_id').annotate(
            quantity=Sum('availability_quantity'),
            missing=Count('pk', filter=Q(availability_quantity__isnull=True)),
        )
        products = products.annotate(
            available_quantity=Coalesce(Subquery(totals.values('quantity')[:1]), Value(0), output_field=BigIntegerField()),
            unconfigured_variant_count=Coalesce(Subquery(totals.values('missing')[:1]), Value(0)),
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
        if state == "published":
            products = products.filter(is_active=True)
        elif state == "review":
            products = products.filter(is_active=False, editorial_state="review")
        elif state == "draft":
            products = products.filter(is_active=False).exclude(editorial_state="review")
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
            selected_state=state,
            brands=Brand.objects.order_by("name", "pk"),
            categories=Category.objects.order_by("slug", "pk"),
            page_query=parameters.urlencode(),
            stock_mode=stock_mode(),
        )
        return context
