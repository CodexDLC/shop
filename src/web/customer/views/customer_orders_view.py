from django.core.paginator import Paginator

from web.catalog.recommendations import collection_suggestions
from web.orders.models import Order

from .customer_page_view import CustomerPageView


class CustomerOrdersView(CustomerPageView):
    template_name = "customer/orders.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["customer_orders"] = Paginator(
            Order.objects.filter(user=self.request.user, is_test=True).order_by("-created_at", "-pk"), 12,
        ).get_page(self.request.GET.get("page"))
        context["collection_suggestions"] = collection_suggestions()
        return context
