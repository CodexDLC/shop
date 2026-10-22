from .base_view import SeoWorkspaceView
from .selectors import workspace_summary


class SeoOverviewView(SeoWorkspaceView):
    template_name = "staff/seo/overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["summary"], context["recent_pages"] = workspace_summary(self.content_language())
        return context
