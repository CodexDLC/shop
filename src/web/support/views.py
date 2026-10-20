from web.storefront.page_view import StorefrontPageView


class SupportPageView(StorefrontPageView):
    def get_context_data(self, **kwargs):
        from .forms import ContactForm

        context = super().get_context_data(**kwargs)
        context.setdefault("contact_form", ContactForm())
        return context
