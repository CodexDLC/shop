from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect

from web.cart.models import PromoCode
from web.localization import translate_text
from web.staff.audit import record_staff_action
from web.staff.views.staff_page_view import StaffPageView

from .editing import check_state, issue_state
from .promo_form import PromoForm


class PromoEditView(PermissionRequiredMixin, StaffPageView):
    template_name = "staff/operations/promo_form.html"
    cabinet_module = "management"
    http_method_names = ["get", "post", "head", "options"]

    def get_permission_required(self):
        action = "change" if self.kwargs.get("pk") else "add"
        return ("cart.view_promocode", f"cart.{action}_promocode")

    def render_editor(self, obj=None, form=None, *, status=200):
        if form is None:
            form = PromoForm(instance=obj, initial={"original_state": issue_state("cart.promocode", obj)})
        return self.render_to_response(self.get_context_data(form=form, promo=obj), status=status)

    def get(self, request, pk=None):
        return self.render_editor(get_object_or_404(PromoCode, pk=pk) if pk else None)

    def post(self, request, pk=None):
        form = None
        obj = None
        try:
            with transaction.atomic():
                if pk:
                    obj = get_object_or_404(PromoCode.objects.select_for_update(), pk=pk)
                if not check_state("cart.promocode", request.POST.get("original_state", ""), obj):
                    form = PromoForm(request.POST, instance=obj)
                    form.is_valid()
                    form.add_error(None, translate_text("staff.records.stale"))
                    return self.render_editor(obj, form, status=409)
                form = PromoForm(request.POST, instance=obj)
                if not form.is_valid():
                    return self.render_editor(obj, form, status=400)
                saved = form.save()
                record_staff_action(request, "promo.updated" if pk else "promo.created", saved)
        except IntegrityError:
            # Uniqueness may change between validation and INSERT on a new code.
            form.add_error(None, translate_text("staff.records.invalid"))
            return self.render_editor(obj, form, status=400)
        messages.success(request, translate_text("staff.records.saved"))
        return redirect("staff:promo_detail", pk=saved.pk)
