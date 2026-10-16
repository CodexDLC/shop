from django.contrib.auth.mixins import LoginRequiredMixin

from web.customer.forms import CustomerAddressForm, ProfileForm
from web.localization import translate_text
from web.localization.translation import source_messages
from web.storefront.page_view import StorefrontPageView


class CustomerPageView(LoginRequiredMixin, StorefrontPageView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["customer_display_name"] = self.request.user.get_full_name() or self.request.user.get_username()
        context["customer_section"] = {
            "overview": "overview", "orders": "orders", "order_detail": "orders", "profile": "profile",
        }.get(self.request.resolver_match.url_name, "overview")
        context["shop_texts"].update({key: translate_text(key) for key in source_messages()
                                     if key.startswith(("customer.account.", "customer.address."))})
        addresses = list(self.request.user.customer_addresses.all())
        context.setdefault("customer_addresses", addresses)
        context.setdefault("customer_default_address", next((address for address in addresses if address.is_default), None))
        context.setdefault("customer_address_data", [
            {field: getattr(address, field) for field in (
                "id", "kind", "recipient", "street_address", "post_number", "station_number",
                "postal_code", "city", "country", "is_default",
            )} for address in addresses
        ])
        context.setdefault("profile_form", ProfileForm(instance=self.request.user))
        context.setdefault("address_form", CustomerAddressForm())
        context.setdefault("address_modal_open", False)
        context.setdefault("address_edit_id", None)
        context.setdefault("active_tab", "tab-profile")
        if self.template_name == "customer/profile.html":
            context["customer_section"] = "profile"
        return context

