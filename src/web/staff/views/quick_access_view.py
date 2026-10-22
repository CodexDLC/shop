import hashlib
import json

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core import signing
from django.db import IntegrityError, transaction
from django.db.models import F
from django.shortcuts import redirect

from web.localization import translate_text
from web.staff.audit import record_staff_action
from web.staff.forms.quick_access_form import QuickAccessForm
from web.staff.models import CabinetPreferences
from web.staff.settings_workspace import settings_workspace

from .staff_page_view import StaffPageView


class QuickAccessView(PermissionRequiredMixin, StaffPageView):
    permission_required = "staff.change_cabinetpreferences"
    cabinet_module = "management"
    template_name = "staff/settings.html"
    state_salt = "staff.shared-quick-access.v1"

    @staticmethod
    def fingerprint(keys):
        return hashlib.sha256(json.dumps(keys, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()

    def state(self, preferences):
        return {"actor": str(self.request.user.pk), "exists": preferences is not None,
                "revision": preferences.revision if preferences else 0,
                "fingerprint": self.fingerprint(preferences.quick_access_keys if preferences else [])}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(settings_workspace(self.request.user, "quick_access"))
        preferences = CabinetPreferences.objects.filter(pk=1).first()
        context["form"] = kwargs.get("form") or QuickAccessForm(
            user=self.request.user, initial={"links": preferences.quick_access_keys if preferences else [],
                                           "state": signing.dumps(self.state(preferences), salt=self.state_salt)})
        return context

    def conflict(self, form):
        form.add_error(None, translate_text("staff.settings.conflict"))
        return self.render_to_response(self.get_context_data(form=form), status=409)

    def post(self, request, *args, **kwargs):
        form = QuickAccessForm(request.POST, user=request.user)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form), status=400)
        try:
            submitted = signing.loads(form.cleaned_data["state"], salt=self.state_salt, max_age=7200)
        except signing.BadSignature:
            return self.conflict(form)
        with transaction.atomic():
            preferences = CabinetPreferences.objects.filter(pk=1).first()
            if submitted != self.state(preferences):
                return self.conflict(form)
            editable = {key for key, _ in form.fields["links"].choices}
            old_keys = preferences.quick_access_keys if preferences else []
            # Shared pins outside the editor's current permissions are never removed.
            submitted_keys = form.cleaned_data["links"]
            selected = list(dict.fromkeys(
                [key for key in old_keys if key not in editable or key in submitted_keys]
                + [key for key in submitted_keys if key not in old_keys]
            ))
            if preferences:
                changed = CabinetPreferences.objects.filter(
                    pk=1, revision=preferences.revision, quick_access_keys=old_keys,
                ).update(quick_access_keys=selected, revision=F("revision") + 1)
                if not changed:
                    return self.conflict(form)
            else:
                try:
                    # The unique singleton PK closes the concurrent first-save race.
                    with transaction.atomic():
                        preferences = CabinetPreferences.objects.create(pk=1, quick_access_keys=selected, revision=1)
                except IntegrityError:
                    return self.conflict(form)
            record_staff_action(request, "quick_access.updated", preferences)
        messages.success(request, translate_text("staff.settings.saved"))
        return redirect("staff:settings")
