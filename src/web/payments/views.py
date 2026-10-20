from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from codex_ecommerce.cart import CartError
from web.cart.session_cart import quote
from web.orders.address_form import CheckoutAddressForm
from web.orders.checkout_state import address_key, review_token
from web.orders.persistence import create_test_order
from web.storefront.page_view import StorefrontPageView


@method_decorator(never_cache, name="dispatch")
class PaymentPageView(StorefrontPageView):
    template_name = "payments/review.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = quote(self.request)
        address = self.request.session.get(address_key(self.request), {})
        context.update(cart=cart, checkout_address=address, checkout_token=review_token(self.request, cart, address))
        return context

    def get(self, request, *args, **kwargs):
        if not quote(request)["can_checkout"]:
            return redirect("cart:detail")
        if not CheckoutAddressForm(request.session.get(address_key(request), {})).is_valid():
            return redirect("orders:address")
        if not request.session.get(address_key(request) + "_nonce"):
            return redirect("orders:address")
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if request.POST.get("method") != "test":
            return self.render_to_response(self.get_context_data(checkout_error="commerce.error.method"), status=400)
        try:
            order = create_test_order(request, request.POST.get("checkout_token", ""))
        except CartError as exc:
            return self.render_to_response(self.get_context_data(checkout_error=str(exc)), status=409)
        return redirect(reverse("orders:confirmation") + f"?reference={order.reference}")
