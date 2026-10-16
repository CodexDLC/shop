import hashlib
import json

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core import signing
from django.db import IntegrityError, transaction
from django.forms import formset_factory
from django.forms.utils import ErrorList
from django.shortcuts import get_object_or_404, redirect

from web.catalog.models import Product, ProductVariant
from web.localization.translation import translate_text
from web.staff.audit import record_staff_action
from web.staff.forms.variant_form import VariantForm
from web.staff.forms.variant_formset import VariantFormSet
from web.staff.views.staff_page_view import StaffPageView


class VariantMatrixView(PermissionRequiredMixin, StaffPageView):
    permission_required = ("catalog.change_product", "catalog.change_productvariant")
    template_name = "staff/variants.html"
    cabinet_module = "catalog"
    http_method_names = ["get", "post", "head", "options"]
    fields = ("id", "sku", "color_code", "color_name_key", "color_hex", "size", "price",
              "currency", "demo_quantity", "is_active")

    def rows(self, product):
        return list(product.variants.order_by("pk").values(*self.fields))

    def fingerprint(self, product, rows):
        payload = json.dumps([product.pk, rows], sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()

    def make_formset(self, rows, data=None, *, requires_active=False):
        factory = formset_factory(VariantForm, formset=VariantFormSet, extra=1,
                                  max_num=100, validate_max=True, absolute_max=100)
        return factory(data=data, initial=rows, prefix="variants", expected_ids=[row["id"] for row in rows],
                       can_add=self.request.user.has_perm("catalog.add_productvariant"),
                       requires_active=requires_active)

    def render_editor(self, product, rows, formset, *, status=200):
        fingerprint = signing.dumps(self.fingerprint(product, rows), salt="staff-variant-matrix")
        if self.request.method == "POST" and status == 409:
            # Do not authorize an old bound form against the new database snapshot.
            fingerprint = self.request.POST.get("fingerprint", "")
        context = self.get_context_data(product=product, formset=formset,
                                       fingerprint=fingerprint)
        return self.render_to_response(context, status=status)

    def get(self, request, *args, **kwargs):
        product = get_object_or_404(Product, pk=kwargs["pk"])
        rows = self.rows(product)
        return self.render_editor(product, rows, self.make_formset(rows, requires_active=product.is_active))

    def post(self, request, *args, **kwargs):
        status = 400
        try:
            with transaction.atomic():
                product = get_object_or_404(Product.objects.select_for_update(), pk=kwargs["pk"])
                rows = self.rows(product)
                formset = self.make_formset(rows, request.POST, requires_active=product.is_active)
                valid = formset.is_valid()
                try:
                    submitted = signing.loads(request.POST.get("fingerprint", ""),
                                              salt="staff-variant-matrix", max_age=28800)
                except signing.BadSignature:
                    submitted = None
                if submitted != self.fingerprint(product, rows):
                    formset._non_form_errors = ErrorList([translate_text("staff.variants.stale")])
                    status = 409
                elif valid:
                    for form in formset:
                        if not form.cleaned_data:
                            continue
                        values = form.cleaned_data.copy()
                        variant_id = values.pop("id", None)
                        if variant_id:
                            values.pop("sku")
                            ProductVariant.objects.filter(pk=variant_id, product=product).update(**values)
                        else:
                            ProductVariant.objects.create(product=product, **values)
                    record_staff_action(request, "variants.updated", product)
                    messages.success(request, translate_text("staff.variants.saved"))
                    return redirect("staff:variants", pk=product.pk)
        except IntegrityError:
            formset._non_form_errors = ErrorList([translate_text("staff.variants.conflict")])
            status = 409
        return self.render_editor(product, rows, formset, status=status)
