from web.customer.views import CustomerPageView
from web.orders.models import Order


class CustomerOverviewView(CustomerPageView):
    template_name = "customer/overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        orders = Order.objects.filter(user=self.request.user, is_test=True)
        context["customer_order_count"] = orders.count()
        context["customer_latest_order"] = orders.order_by("-created_at", "-pk").first()
        return context
