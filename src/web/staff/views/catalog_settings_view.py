from django.contrib.auth.mixins import PermissionRequiredMixin

from .staff_page_view import StaffPageView


class CatalogSettingsView(PermissionRequiredMixin, StaffPageView):
    permission_required = "catalog.view_product"
    cabinet_module = "catalog"
    template_name = "staff/catalog_settings.html"
