from django.shortcuts import get_object_or_404
from django.utils import timezone

from web.inventory.models import InventoryMovement, ReservationLine
from web.staff.views.staff_page_view import StaffPageView

from .access import READ_PERMISSIONS, selected_section
from .cleanup_form import CleanupForm
from .intents import issue_intent
from .selectors import bounded_page, history_rows, reconciliation, reservation_rows, variants
from .stock_form import StockForm


class InventoryDetailView(StaffPageView):
    template_name = 'staff/inventory/detail.html'
    cabinet_module = 'operations'
    http_method_names = ['get', 'head', 'options']

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.section = selected_section(request.user, request.GET.get('section'))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        balance = self.section == 'balance'
        variant = get_object_or_404(variants(balance=balance), pk=self.kwargs['pk'])
        forms = {}
        if balance and variant.is_active:
            for action in ('initialize',) if variant.stock_on_hand is None else ('receive', 'adjust'):
                if user.has_perm(f'inventory.{action}_stockbalance'):
                    forms[action] = StockForm(action=action, prefix=action, initial={
                        'intent': issue_intent(user, variant.pk, action, variant.stock_revision or 0),
                        'quantity': variant.stock_on_hand if action == 'adjust' else None})
        context.update(variant=variant, section=self.section, show_balance=balance, inventory_forms=forms,
            tabs=[section for section, permission in READ_PERMISSIONS.items() if user.has_perm('inventory.' + permission)])
        if balance and all(user.has_perm('inventory.' + p) for p in READ_PERMISSIONS.values()):
            context['reconciliation'] = reconciliation(variant.pk)
        if self.section == 'history':
            context['history_page'] = bounded_page(history_rows(variant.pk), self.request.GET.get('page'))
        if self.section == 'reservations':
            context['reservation_page'] = bounded_page(reservation_rows(variant.pk), self.request.GET.get('page'))
            context['expired_count'] = ReservationLine.objects.filter(variant_id=variant.pk, location_id='main',
                state='held', expires_at__lte=timezone.now()).count()
            if user.has_perm('inventory.expire_reservationline'):
                context['cleanup_form'] = CleanupForm(prefix='expire',
                    initial={'intent': issue_intent(user, variant.pk, 'expire', 0)})
        if user.has_perm('inventory.view_inventorymovement'):
            context['last_cleanup'] = InventoryMovement.objects.filter(variant_id=variant.pk,
                kind='expire', location_id='main').order_by('-pk').values_list('created_at', flat=True).first()
        return context
