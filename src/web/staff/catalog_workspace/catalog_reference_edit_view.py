import json

from django.contrib import messages
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse

from web.localization.translation import translate_text
from web.staff.audit import record_staff_action
from web.staff.views.staff_page_view import StaffPageView

from .forms import guide_rows, reference_form
from .registry import RESOURCES


class CatalogReferenceEditView(StaffPageView):
    cabinet_module = "catalog"
    template_name = "staff/catalog_workspace/form.html"
    resource = None
    http_method_names = ["get", "post", "head", "options"]

    def dispatch(self, request, *args, **kwargs):
        model, _, fields = RESOURCES[self.resource]
        if not fields or (not kwargs.get("pk") and self.resource in ("categories", "tags")):
            raise PermissionDenied
        permission = "change" if kwargs.get("pk") else "add"
        if request.user.is_authenticated and not request.user.has_perm(f"catalog.{permission}_{model._meta.model_name}"):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def snapshot(self, obj):
        if obj is None:
            return None
        state = list(type(obj).objects.filter(pk=obj.pk).values())
        if self.resource == "size_guides":
            state += list(obj.rows.order_by("pk").values())
        return signing.dumps(json.loads(json.dumps(state, default=str)), salt="staff-reference", compress=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        model, singular, _ = RESOURCES[self.resource]
        obj = kwargs.get("object")
        if obj is None and self.kwargs.get("pk"):
            obj = get_object_or_404(model, pk=self.kwargs["pk"])
        context.update(
            object=obj, form=kwargs.get("form") or reference_form(self.resource, instance=obj),
            resource=self.resource, title_key=f"staff.workspace_catalog.{self.resource}",
            original_state=self.snapshot(obj), back_url=reverse(f"staff:{self.resource}"),
        )
        if self.resource == "size_guides":
            context["formset"] = kwargs.get("formset") or guide_rows(instance=obj)
        return context

    def post(self, request, *args, **kwargs):
        model, singular, _ = RESOURCES[self.resource]
        obj = None
        formset = None
        saved = False
        try:
            with transaction.atomic():
                if kwargs.get("pk"):
                    obj = get_object_or_404(model.objects.select_for_update(), pk=kwargs["pk"])
                form = reference_form(self.resource, request.POST, instance=obj)
                valid = form.is_valid()
                if obj is not None:
                    try:
                        submitted = signing.loads(request.POST.get("original_state", ""), salt="staff-reference", max_age=7200)
                        current = signing.loads(self.snapshot(obj), salt="staff-reference")
                        if submitted != current:
                            raise signing.BadSignature
                    except signing.BadSignature:
                        form.add_error(None, translate_text("staff.workspace_catalog.stale"))
                        form.workspace_notice = translate_text("staff.workspace_catalog.stale")
                        valid = False
                    if self.resource != "size_guides":
                        # Serialize against the product publication workflow, which locks its product.
                        linked = list(obj.products.select_for_update().only("pk", "is_active"))
                        if any(product.is_active for product in linked):
                            form.add_error(None, translate_text("staff.workspace_catalog.published_block"))
                            form.workspace_notice = translate_text("staff.workspace_catalog.published_block")
                            valid = False
                if self.resource == "size_guides":
                    formset = guide_rows(request.POST, instance=form.instance)
                    valid = formset.is_valid() and valid
                    for row in formset.forms:
                        if row.has_changed():
                            action = "change" if row.instance.pk else "add"
                            if not request.user.has_perm(f"catalog.{action}_sizeguiderow"):
                                raise PermissionDenied
                if valid:
                    obj = form.save()
                    if formset is not None:
                        formset.instance = obj
                        formset.save()
                    record_staff_action(request, f"reference.{singular}.saved", obj)
                    saved = True
        except IntegrityError:
            form.add_error(None, translate_text("staff.workspace_catalog.conflict"))
            form.workspace_notice = translate_text("staff.workspace_catalog.conflict")
        if saved:
            messages.success(request, translate_text("staff.workspace_catalog.saved"))
            return HttpResponseRedirect(reverse(f"staff:{singular}_detail", kwargs={"pk": obj.pk}))
        return self.render_to_response(self.get_context_data(object=obj, form=form, formset=formset), status=400)
