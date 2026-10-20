from django.core.exceptions import ValidationError
from django.http import Http404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from web.orders.checkout_state import session_owner
from web.orders.models import Order
from web.storefront.page_view import StorefrontPageView


@method_decorator(never_cache, name="dispatch")
class OrderConfirmationView(StorefrontPageView):
    template_name = "orders/confirmation.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reference = self.request.GET.get("reference")
        if not reference:
            raise Http404
        try:
            orders = Order.objects.filter(reference=reference, is_test=True).prefetch_related("lines")
        except (ValueError, TypeError, ValidationError):
            raise Http404 from None
        if self.request.user.is_authenticated:
            orders = orders.filter(user=self.request.user)
        else:
            orders = orders.filter(user__isnull=True, session_owner=session_owner(self.request))
        try:
            order = orders.first()
        except (ValueError, TypeError):
            raise Http404 from None
        if order is None:
            raise Http404
        context["order"] = order
        return context
