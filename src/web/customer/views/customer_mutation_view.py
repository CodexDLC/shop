from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View

from .customer_page_view import CustomerPageView


class CustomerMutationView(LoginRequiredMixin, View):
    http_method_names = ["post", "options"]

    def invalid(self, request, **context):
        view = CustomerPageView(template_name="customer/profile.html")
        view.setup(request)
        return view.render_to_response(view.get_context_data(**context), status=400)
