from django.contrib.auth.mixins import PermissionRequiredMixin

from web.staff.views.staff_page_view import StaffPageView

from .category_tree import category_rows, tree_rows


class CategoryListView(PermissionRequiredMixin, StaffPageView):
    permission_required = "catalog.view_category"
    cabinet_module = "catalog"
    template_name = "staff/categories/list.html"
    http_method_names = ["get", "head", "options"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rows = tree_rows(category_rows())
        query = self.request.GET.get("q", "").strip()[:200]
        if query:
            rows = [row for row in rows if query.casefold() in row["path"].casefold()
                    or query.casefold() in row["object"].slug.casefold()]
        context.update(category_rows=rows, search_query=query)
        return context
