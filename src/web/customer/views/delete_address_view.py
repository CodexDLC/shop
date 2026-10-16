from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from web.customer.models import CustomerAddress
from web.localization import translate_text

from .customer_mutation_view import CustomerMutationView


class DeleteAddressView(CustomerMutationView):
    def post(self, request, pk):
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            addresses = CustomerAddress.objects.filter(user=request.user)
            address = get_object_or_404(addresses, pk=pk)
            was_default = address.is_default
            address.delete()
            if was_default:
                next_address = addresses.order_by("pk").first()
                if next_address:
                    addresses.filter(pk=next_address.pk).update(is_default=True)
        messages.success(request, translate_text("customer.account.address.deleted"))
        return redirect(reverse("customer:profile") + "#tab-addresses")
