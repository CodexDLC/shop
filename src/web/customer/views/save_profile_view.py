from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from web.customer.forms import ProfileForm
from web.localization import translate_text

from .customer_mutation_view import CustomerMutationView


class SaveProfileView(CustomerMutationView):
    def post(self, request):
        form = ProfileForm(request.POST, instance=request.user)
        if not form.is_valid():
            return self.invalid(request, profile_form=form, active_tab="tab-profile")
        form.save()
        messages.success(request, translate_text("customer.account.profile.saved"))
        return redirect(reverse("customer:profile") + "#tab-profile")
