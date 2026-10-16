from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db import transaction
from django.shortcuts import redirect

from web.localization import translate_text
from web.staff.audit import record_staff_action
from web.staff.forms.quick_access_form import QuickAccessForm
from web.staff.models import CabinetPreferences

from .staff_page_view import StaffPageView


class QuickAccessView(PermissionRequiredMixin, StaffPageView):
    permission_required = "staff.change_cabinetpreferences"
    cabinet_module = "management"
    template_name = "staff/settings.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        saved = CabinetPreferences.objects.filter(pk=1).values_list("quick_access_keys", flat=True).first() or []
        context["form"] = kwargs.get("form") or QuickAccessForm(user=self.request.user, initial={"links": saved})
        return context

    def post(self, request, *args, **kwargs):
        form = QuickAccessForm(request.POST, user=request.user)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form), status=400)
        with transaction.atomic():
            preferences, _ = CabinetPreferences.objects.update_or_create(pk=1, defaults={"quick_access_keys": form.cleaned_data["links"]})
            record_staff_action(request, "quick_access.updated", preferences)
        messages.success(request, translate_text("staff.settings.saved"))
        return redirect("staff:settings")
