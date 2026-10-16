from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from web.customer.models import CustomerAddress
from web.localization import translate_text

from .customer_mutation_view import CustomerMutationView


class DefaultAddressView(CustomerMutationView):
    def post(self, request, pk):
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            addresses = CustomerAddress.objects.filter(user=request.user)
            address = get_object_or_404(addresses, pk=pk)
            addresses.filter(is_default=True).exclude(pk=pk).update(is_default=False)
            address.is_default = True
            address.save(update_fields=["is_default", "updated_at"])
        messages.success(request, translate_text("customer.account.address.default_saved"))
        return redirect(reverse("customer:profile") + "#tab-addresses")
