from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import Http404
from django.urls import reverse

from web.staff.views.staff_page_view import StaffPageView


class SeoWorkspaceView(PermissionRequiredMixin, StaffPageView):
    permission_required = "seo.view_seopage"
    cabinet_module = "management"
    seo_section = "overview"
    http_method_names = ["get", "head", "options"]

    def content_language(self):
        language = self.request.GET.get("content_language", "de")
        if language not in ("de", "ru"):
            raise Http404
        return language

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(content_language=self.content_language(), seo_section=self.seo_section)
        context["seo_navigation"] = [
            {"label": f"staff.seo.nav.{key}", "url": reverse(f"staff:seo_{name}"),
             "active": self.seo_section == key}
            for key, name in [("overview", "overview"), ("pages", "pages"),
                              ("rules", "rules"), ("indexing", "indexing")]
        ]
        return context
