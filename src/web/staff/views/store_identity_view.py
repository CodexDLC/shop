from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core import signing
from django.shortcuts import redirect

from web.localization import translate_text
from web.shop.models import StoreIdentity
from web.staff.forms.store_identity_form import StoreIdentityForm
from web.staff.services.store_identity import STATE_SALT, identity_state, save_store_identity
from web.staff.settings_workspace import settings_workspace

from .staff_page_view import StaffPageView


class StoreIdentityView(PermissionRequiredMixin, StaffPageView):
    permission_required = "shop.change_storeidentity"
    cabinet_module = "management"
    template_name = "staff/store_identity.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(settings_workspace(self.request.user, "store_settings"))
        identity = StoreIdentity.objects.filter(pk=1).first()
        context["form"] = kwargs.get("form") or StoreIdentityForm(instance=identity, initial={
            "state": signing.dumps(identity_state(self.request.user, identity), salt=STATE_SALT),
        })
        context["settings_cards"] = [card for card in context["settings_cards"] if card["key"] != "company"]
        return context

    def post(self, request, *args, **kwargs):
        form = StoreIdentityForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form), status=400)
        if not save_store_identity(request, form.cleaned_data, form.cleaned_data["state"]):
            form.add_error(None, translate_text("staff.store_identity.conflict"))
            return self.render_to_response(self.get_context_data(form=form), status=409)
        messages.success(request, translate_text("staff.store_identity.saved"))
        return redirect("staff:workspace_preview", section="store_settings")
