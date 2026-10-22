from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404

from web.catalog.models import Category, Product
from web.staff.views.staff_page_view import StaffPageView

from .category_tree import branch_ids, category_rows, tree_rows


class CategoryDetailView(PermissionRequiredMixin, StaffPageView):
    permission_required = "catalog.view_category"
    cabinet_module = "catalog"
    template_name = "staff/categories/detail.html"
    http_method_names = ["get", "head", "options"]
    preview = False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        categories = category_rows()
        category = get_object_or_404(Category, pk=self.kwargs["pk"])
        rows = tree_rows(categories)
        branch = branch_ids(categories, category.pk)
        products = Product.objects.none()
        if self.request.user.has_perm("catalog.view_product"):
            products = Product.objects.filter(category_id__in=branch).select_related("brand", "category").order_by("pk")
        context.update(category=category, preview=self.preview,
                       category_row=next((row for row in rows if row["object"].pk == category.pk), None),
                       child_rows=[row for row in rows if row["object"].parent_id == category.pk],
                       page_obj=Paginator(products, 20).get_page(self.request.GET.get("page")),
                       published_count=sum(row.published_count for row in categories if row.pk in branch),
                       branch_count=sum(row.product_count for row in categories if row.pk in branch))
        return context

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        response["Cache-Control"] = "private, no-store"
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response
