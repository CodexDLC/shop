from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from web.customer.forms import CustomerAddressForm
from web.customer.models import CustomerAddress
from web.localization import translate_text

from .customer_mutation_view import CustomerMutationView


class SaveAddressView(CustomerMutationView):
    def post(self, request, pk=None):
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            addresses = CustomerAddress.objects.filter(user=request.user)
            instance = get_object_or_404(addresses, pk=pk) if pk is not None else CustomerAddress(user=request.user)
            form = CustomerAddressForm(request.POST, instance=instance)
            # User is assigned server-side; ModelForm never accepts it from POST.
            if not form.is_valid():
                return self.invalid(request, address_form=form, address_modal_open=True,
                                    address_edit_id=pk, active_tab="tab-addresses")
            address = form.save(commit=False)
            address.is_default = address.is_default or not addresses.exclude(pk=address.pk).exists()
            if address.is_default:
                addresses.exclude(pk=address.pk).filter(is_default=True).update(is_default=False)
            address.save()
            if not addresses.filter(is_default=True).exists():
                addresses.filter(pk=address.pk).update(is_default=True)
        messages.success(request, translate_text("customer.account.address.saved"))
        return redirect(reverse("customer:profile") + "#tab-addresses")
