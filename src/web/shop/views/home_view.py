from django.views.generic import TemplateView

from web.shop.demo import homepage_demo


class HomeView(TemplateView):
    template_name = "shop/home.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | homepage_demo()
