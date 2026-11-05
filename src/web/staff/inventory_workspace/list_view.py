from web.staff.views.staff_page_view import StaffPageView

from .access import selected_section
from .filter_form import FilterForm
from .selectors import bounded_page, variants


class InventoryListView(StaffPageView):
    template_name = 'staff/inventory/list.html'
    cabinet_module = 'operations'
    http_method_names = ['get', 'head', 'options']

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.section = selected_section(request.user, request.GET.get('section'))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        balance = self.section == 'balance'
        form = FilterForm(self.request.GET, balance=balance)
        data = form.cleaned_data if form.is_valid() else {}
        rows = variants(query=data.get('q', ''), status=data.get('status', ''),
            threshold=data.get('threshold'), balance=balance)
        if form.errors:
            rows = rows.none()
        parameters = self.request.GET.copy()
        parameters.pop('page', None)
        context.update(section=self.section, filter_form=form, show_balance=balance,
            page_obj=bounded_page(rows, self.request.GET.get('page')), page_query=parameters.urlencode())
        return context
