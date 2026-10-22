from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import Http404
from django.urls import reverse

from web.staff.settings_workspace import settings_workspace
from web.staff.workspace_previews import PREVIEWS

from .staff_page_view import StaffPageView


class WorkspacePreviewView(PermissionRequiredMixin, StaffPageView):
    template_name = "staff/workspace_preview.html"
    http_method_names = ["get", "head", "options"]

    def get_permission_required(self):
        try:
            self.cabinet_module, permission, self.capabilities = PREVIEWS[self.kwargs["section"]]
        except KeyError as error:
            raise Http404 from error
        return (permission,)

    def get_template_names(self):
        if self.kwargs["section"] in {"store_settings", "operations_settings"}:
            return ["staff/settings_workspace.html"]
        return super().get_template_names()

    def get_context_data(self, **kwargs):
        section = self.kwargs["section"]
        context = super().get_context_data(**kwargs)
        context.update(
            workspace_section=section, title_key=f"staff.workspace.nav.{section}",
            capabilities=[{"title": f"staff.workspace.capability.{key}",
                           "description": f"staff.workspace.capability.{key}.description"}
                          for key in self.capabilities],
        )
        if section in {"store_settings", "operations_settings"}:
            context.update(settings_workspace(self.request.user, section))
            return context
        if section == "content":
            context["existing_links"] = [
                {"url": reverse("support:legal"), "label": "staff.workspace.capability.legal"},
                {"url": reverse("support:emails"), "label": "staff.workspace.capability.email"},
            ]
        context["design_fields"] = {
            "shipping": ("contract", "parcel", "label_format"),
            "returns": ("return_window", "inspection", "return_rules"),
            "analytics": ("period", "sources", "profit"),
            "content": ("homepage", "languages", "email"),
            "integrations": ("provider", "environment", "connection_status"),
            "store_settings": ("company", "vat", "languages", "documents"),
            "operations_settings": ("packing", "shipping_rules", "notifications"),
        }[section]
        return context
