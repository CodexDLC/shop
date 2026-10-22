from django.contrib.auth.mixins import PermissionRequiredMixin

from web.staff.settings_workspace import settings_workspace

from .staff_page_view import StaffPageView


class CatalogSettingsView(PermissionRequiredMixin, StaffPageView):
    permission_required = "catalog.view_product"
    cabinet_module = "catalog"
    template_name = "staff/settings_workspace.html"
    http_method_names = ["get", "head", "options"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(settings_workspace(self.request.user, "catalog"))
        return context
