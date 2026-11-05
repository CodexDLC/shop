from codex_django.cabinet import CabinetTemplateView, StaffRequiredMixin

from web.inventory.checkout_policy import stock_mode


class StaffPageView(StaffRequiredMixin, CabinetTemplateView):
    cabinet_space = "staff"
    cabinet_module = "overview"
    raise_exception = False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(SITE_NAME="Männermasche", LANGUAGE_CODE=self.request.LANGUAGE_CODE, stock_mode=stock_mode())
        return context
