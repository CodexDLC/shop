import secrets

from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from web.cart.session_cart import quote
from web.orders.address_form import CheckoutAddressForm
from web.orders.checkout_state import address_key, session_owner
from web.storefront.page_view import StorefrontPageView


@method_decorator(never_cache, name="dispatch")
class OrderPageView(StorefrontPageView):
    template_name = "orders/address.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cart"] = quote(self.request)
        context.setdefault("address_form", CheckoutAddressForm(initial=self.request.session.get(
            address_key(self.request), {"country": "DE"})))
        return context

    def get(self, request, *args, **kwargs):
        if not quote(request)["can_checkout"]:
            return redirect("cart:detail")
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not quote(request)["can_checkout"]:
            return redirect("cart:detail")
        form = CheckoutAddressForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(address_form=form), status=400)
        request.session[address_key(request)] = form.cleaned_data
        session_owner(request)
        request.session[address_key(request) + "_nonce"] = secrets.token_hex(16)
        return redirect("payments:review")
