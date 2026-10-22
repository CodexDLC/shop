from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone

from web.catalog.models import Product
from web.localization import translate_text
from web.staff.audit import record_staff_action
from web.staff.product_editing import check_state, content_fingerprint, issue_state, publication_issues
from web.staff.views.staff_page_view import StaffPageView


class ProductPublicationView(PermissionRequiredMixin, StaffPageView):
    permission_required = ('catalog.view_product', 'catalog.change_product')
    template_name = 'staff/product_publication.html'
    cabinet_module = 'catalog'
    http_method_names = ['get', 'post', 'head', 'options']

    def render_editor(self, product, *, error=None, status=200):
        return self.render_to_response(self.get_context_data(
            product=product, original_state=issue_state(product), issues=publication_issues(product), error=error,
        ), status=status)

    def get(self, request, pk):
        return self.render_editor(get_object_or_404(Product, pk=pk))

    def post(self, request, pk):
        action = request.POST.get('action')
        if action in ('publish', 'withdraw') and not request.user.has_perm('catalog.publish_product'):
            raise PermissionDenied
        with transaction.atomic():
            product = get_object_or_404(Product.objects.select_for_update(), pk=pk)
            if not check_state(product, request.POST.get('original_state', '')):
                return self.render_editor(product, error='staff.product_form.stale', status=409)
            if action == 'withdraw' and product.is_active:
                product.is_active = False
                product.editorial_state = 'draft'
                product.review_fingerprint = ''
            elif action == 'review' and not product.is_active:
                if publication_issues(product):
                    return self.render_editor(product, error='staff.workflow.incomplete', status=400)
                product.editorial_state = 'review'
                product.review_fingerprint = content_fingerprint(product)
            elif action == 'publish' and not product.is_active:
                if (product.editorial_state != 'review' or publication_issues(product)
                        or product.review_fingerprint != content_fingerprint(product)):
                    return self.render_editor(product, error='staff.workflow.review_again', status=409)
                product.is_active = True
                product.editorial_state = 'published'
                product.review_fingerprint = ''
                if product.published_at is None:
                    product.published_at = timezone.now()
            else:
                return self.render_editor(product, error='staff.workflow.invalid_action', status=409)
            product.save(update_fields=['is_active', 'editorial_state', 'review_fingerprint', 'published_at'])
            record_staff_action(request, f'product.{action}', product)
        messages.success(request, translate_text('staff.workflow.saved'))
        return redirect('staff:product_publication', pk=pk)
