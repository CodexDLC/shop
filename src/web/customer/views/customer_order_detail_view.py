from django.shortcuts import get_object_or_404, redirect

from web.orders.models import Order

from .customer_page_view import CustomerPageView


class CustomerOrderDetailView(CustomerPageView):
    template_name = "customer/order_detail.html"

    def get(self, request, *args, **kwargs):
        if "reference" not in kwargs:
            return redirect("customer:orders")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["customer_order"] = get_object_or_404(
            Order.objects.prefetch_related("lines"), user=self.request.user, is_test=True,
            reference=self.kwargs["reference"],
        )
        context["test_order_stages"] = (
            "customer.test_orders.stage_saved", "customer.test_orders.stage_payment",
            "customer.test_orders.stage_shipping", "customer.test_orders.stage_delivery",
        )
        return context
