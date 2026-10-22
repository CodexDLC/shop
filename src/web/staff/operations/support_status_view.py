from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect

from web.localization import translate_text
from web.staff.audit import record_staff_action
from web.staff.views.staff_page_view import StaffPageView
from web.support.models import ContactTicket

from .editing import check_state
from .support_status_form import SupportStatusForm


class SupportStatusView(PermissionRequiredMixin, StaffPageView):
    permission_required = ("support.view_contactticket", "support.change_contactticket")
    cabinet_module = "operations"
    http_method_names = ["post", "options"]

    def post(self, request, pk):
        form = SupportStatusForm(request.POST)
        if not form.is_valid():
            return HttpResponse(translate_text("staff.records.invalid"), status=400)
        with transaction.atomic():
            ticket = get_object_or_404(ContactTicket.objects.select_for_update(), pk=pk)
            if not check_state("support.contactticket", form.cleaned_data["original_state"], ticket):
                return HttpResponse(translate_text("staff.records.stale"), status=409)
            resolved = form.cleaned_data["action"] == "resolve"
            if ticket.resolved == resolved:
                return HttpResponse(translate_text("staff.records.stale"), status=409)
            ticket.resolved = resolved
            try:
                ticket.full_clean()
            except ValidationError:
                return HttpResponse(translate_text("staff.records.invalid"), status=400)
            ticket.save(update_fields=["resolved"])
            record_staff_action(request, "support.resolved" if resolved else "support.reopened", ticket)
        messages.success(request, translate_text("staff.records.saved"))
        return redirect("staff:support_detail", pk=pk)
