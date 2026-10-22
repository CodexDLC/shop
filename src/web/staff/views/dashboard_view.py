from web.staff.dashboard_context import dashboard_context

from .staff_page_view import StaffPageView


class DashboardView(StaffPageView):
    template_name = "staff/dashboard.html"

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), **dashboard_context(self.request.user)}
