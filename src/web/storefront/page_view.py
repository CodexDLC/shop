from django.urls import reverse
from django.views.generic import TemplateView

from web.cart.demo import get_cart_demo_context
from web.catalog.demo import get_catalog_demo_context
from web.localization import translate_text
from web.localization.translation import source_messages
from web.orders.demo import get_order_demo_context
from web.payments.demo import get_payment_demo_context
from web.storefront.pages import page_manifest


class StorefrontPageView(TemplateView):
    """Read-only composition boundary; demo contexts cannot execute commerce."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_cart_demo_context())
        context.update(get_catalog_demo_context())
        context.update(get_order_demo_context())
        context.update(get_payment_demo_context())
        context['shop_routes'] = {
            page['source']: reverse(f"{page['feature']}:{page['name']}") for page in page_manifest()
        }
        context['demo_mode'] = True
        namespace = self.template_name.replace('/', '.').removesuffix('.html')
        prefixes = (namespace + '.', 'layout.', 'navigation.', 'demo.', 'home.hero.')
        context['shop_texts'] = {
            key: translate_text(key) for key in source_messages() if key.startswith(prefixes)
        }
        return context
