from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone

from codex_ecommerce.inventory import InventoryError, OperationContext
from web.inventory import services
from web.inventory.access import require_actor
from web.inventory.expiry_service import expire_due_reservations
from web.localization import translate_text

from .cleanup_form import CleanupForm
from .detail_view import InventoryDetailView
from .intents import read_intent
from .stock_form import StockForm


class InventoryCommandView(InventoryDetailView):
    http_method_names = ['post', 'options']

    def dispatch(self, request, *args, **kwargs):
        action = kwargs['action']
        if action not in {'initialize', 'receive', 'adjust', 'expire'}:
            raise Http404
        if request.user.is_authenticated:
            require_actor(request.user, 'expire_reservationline' if action == 'expire' else action + '_stockbalance')
            require_actor(request.user, 'view_reservationline' if action == 'expire' else 'view_stockbalance')
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        action = kwargs['action']
        self.section = 'reservations' if action == 'expire' else 'balance'
        form = (CleanupForm(request.POST, prefix=action) if action == 'expire'
            else StockForm(request.POST, prefix=action, action=action))
        status = 400
        domain_error = None
        if form.is_valid():
            try:
                intent = read_intent(form.cleaned_data['intent'], request.user, kwargs['pk'], action)
                if action == 'expire':
                    summary = expire_due_reservations(actor=request.user, now=timezone.now(), batch_size=20)
                    messages.success(request, translate_text('staff.inventory.cleanup_result',
                        scanned=summary.scanned, expired=summary.expired, skipped=summary.skipped,
                        more=translate_text('staff.inventory.yes' if summary.has_more else 'staff.inventory.no')))
                else:
                    result = getattr(services, action)(actor=request.user, variant_id=kwargs['pk'],
                        quantity=form.cleaned_data['quantity'], context=OperationContext(intent['key'], 'staff',
                            str(request.user.pk), form.cleaned_data['reason'], intent['revision']))
                    messages.success(request, translate_text('staff.inventory.saved', on_hand=result.on_hand,
                        reserved=result.reserved, available=result.available, revision=result.revision))
                return HttpResponseRedirect(reverse('staff:stock_detail', kwargs={'pk': kwargs['pk']})
                    + ('?section=reservations' if action == 'expire' else ''))
            except ValidationError as error:
                form.add_error(None, error)
            except InventoryError as error:
                domain_error = error
                status = 409
            except DatabaseError:
                form.add_error(None, translate_text('staff.inventory.error.database'))
                status = 503
        context = self.get_context_data()
        if domain_error is not None:
            key = 'staff.inventory.error.' + domain_error.code
            variant = context['variant']
            # Explain the authoritative rejection using a fresh rendering
            # snapshot. Never preempt service CAS/replay or replace stale errors.
            if (action == 'adjust' and domain_error.code == 'inventory_invariant' and variant.is_active
                    and variant.stock_reserved is not None
                    and form.cleaned_data['quantity'] < variant.stock_reserved):
                message = translate_text('staff.inventory.error.below_reserved',
                    quantity=form.cleaned_data['quantity'], reserved=variant.stock_reserved)
                context['below_reserved'] = True
            else:
                message = translate_text(key)
            form.add_error(None, message)
        if action == 'expire':
            context['cleanup_form'] = form
        else:
            context['inventory_forms'][action] = form
        return self.render_to_response(context, status=status)
