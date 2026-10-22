from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect

from web.catalog.models import Product, SizeGuide
from web.localization import translate_text
from web.staff.audit import record_staff_action
from web.staff.forms.product_information_form import ProductInformationForm
from web.staff.product_editing import check_state, issue_state, mark_changed, require_editable
from web.staff.views.staff_page_view import StaffPageView


class ProductInformationView(PermissionRequiredMixin, StaffPageView):
    permission_required = ('catalog.change_product', 'catalog.view_productinformation')
    template_name = 'staff/product_information.html'
    cabinet_module = 'catalog'
    http_method_names = ['get', 'post', 'head', 'options']

    def render_editor(self, product, form=None, status=200):
        information = product.information.filter(language_code='de').first()
        form = form if form is not None else ProductInformationForm(
            instance=information, initial={'original_state': issue_state(product)},
        )
        context = self.get_context_data(product=product, form=form, size_guides=SizeGuide.objects.filter(
            brand_id=product.brand_id,
        ).select_related('category'))
        return self.render_to_response(context, status=status)

    def get(self, request, pk):
        return self.render_editor(get_object_or_404(Product, pk=pk))

    def post(self, request, pk):
        with transaction.atomic():
            product = get_object_or_404(Product.objects.select_for_update(), pk=pk)
            require_editable(product)
            information = product.information.filter(language_code='de').first()
            required = 'catalog.change_productinformation' if information else 'catalog.add_productinformation'
            if not request.user.has_perm(required):
                from django.core.exceptions import PermissionDenied
                raise PermissionDenied
            form = ProductInformationForm(request.POST, instance=information)
            valid = form.is_valid()
            if not check_state(product, request.POST.get('original_state', '')):
                form.add_error(None, translate_text('staff.product_form.stale'))
                return self.render_editor(product, form, 409)
            if valid:
                information = form.save(commit=False)
                information.product = product
                information.language_code = 'de'
                information.save()
                mark_changed(product)
                record_staff_action(request, 'product.information_updated', product)
                messages.success(request, translate_text('staff.product_form.saved'))
                return redirect('staff:product_information', pk=pk)
        return self.render_editor(product, form, 400)
