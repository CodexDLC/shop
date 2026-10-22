from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.paginator import Paginator

from web.staff.views.staff_page_view import StaffPageView

from .presentation import columns, table_row
from .registry import record_permission, status_options
from .selectors import records


class RecordListView(PermissionRequiredMixin, StaffPageView):
    template_name = "staff/operations/list.html"
    http_method_names = ["get", "head", "options"]
    kind = "orders"
    cabinet_module = "operations"

    def get_permission_required(self):
        return (record_permission(self.kind),)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "").strip()[:200]
        options = status_options(self.kind)
        status = self.request.GET.get("status", "")
        if status not in dict(options):
            status = ""
        page = Paginator(records(self.kind, query, status), 25).get_page(self.request.GET.get("page"))
        parameters = self.request.GET.copy()
        parameters.pop("page", None)
        context.update(title_key=f"staff.records.{self.kind}", kind=self.kind, columns=columns(self.kind),
                       rows=[table_row(self.kind, obj, self.request.user) for obj in page.object_list], page_obj=page,
                       search_query=query, status_options=options, selected_status=status,
                       page_query=parameters.urlencode())
        return context
