from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse

from web.catalog.models import Product
from web.localization.translation import translate_text
from web.staff.audit import record_staff_action
from web.staff.forms.product_form import ProductForm
from web.staff.product_editing import mark_changed, require_editable
from web.staff.views.staff_page_view import StaffPageView


class ProductEditView(StaffPageView):
    template_name = "staff/product_form.html"
    cabinet_module = "catalog"
    http_method_names = ["get", "post", "head", "options"]

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            permission = "catalog.change_product" if kwargs.get("pk") else "catalog.add_product"
            if not request.user.has_perm(permission):
                raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = kwargs.get("product")
        if product is None and self.kwargs.get("pk"):
            product = get_object_or_404(Product, pk=self.kwargs["pk"])
        context.update(product=product, form=kwargs.get("form") or ProductForm(instance=product))
        return context

    def post(self, request, *args, **kwargs):
        form = None
        product = None
        saved = False
        try:
            with transaction.atomic():
                if kwargs.get("pk"):
                    product = get_object_or_404(Product.objects.select_for_update(), pk=kwargs["pk"])
                    require_editable(product)
                form = ProductForm(request.POST, instance=product)
                if form.is_valid():
                    product = form.save()
                    mark_changed(product)
                    record_staff_action(
                        request, "product.updated" if kwargs.get("pk") else "product.created", product,
                    )
                    saved = True
        except IntegrityError:
            if form is None:
                raise
            saved = False
            form.add_error(None, translate_text("staff.product_form.conflict"))
        if saved:
            messages.success(request, translate_text("staff.product_form.saved"))
            return HttpResponseRedirect(reverse("staff:product_edit", kwargs={"pk": product.pk}))
        return self.render_to_response(self.get_context_data(form=form, product=product), status=400)
