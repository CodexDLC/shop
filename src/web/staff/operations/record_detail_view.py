from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import Http404
from django.urls import reverse

from web.staff.views.staff_page_view import StaffPageView

from .editing import issue_state
from .order_presentation import order_context
from .record_presentation import record_card
from .registry import record_model, record_permission
from .selectors import record_detail


class RecordDetailView(PermissionRequiredMixin, StaffPageView):
    template_name = "staff/operations/detail.html"
    http_method_names = ["get", "head", "options"]
    kind = "orders"
    cabinet_module = "operations"

    def get_permission_required(self):
        return (record_permission(self.kind),)

    def get_template_names(self):
        if self.kind == "orders":
            return ["staff/operations/order_detail.html"]
        return super().get_template_names()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        try:
            obj = record_detail(self.kind, self.kwargs["pk"], user)
        except record_model(self.kind).DoesNotExist:
            raise Http404 from None
        context.update(kind=self.kind, title_key=f"staff.records.{self.kind}",
                       list_url=reverse(f"staff:{self.kind}"), record_id=obj.pk)
        if self.kind == "orders":
            context["order_detail"] = order_context(obj, user)
        else:
            context["card"] = record_card(self.kind, obj, user)
        if self.kind == "support" and user.has_perm("support.change_contactticket"):
            context["support_state"] = issue_state("support.contactticket", obj)
            context["support_resolved"] = obj.resolved
        return context

