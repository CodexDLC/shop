from urllib.parse import urlencode

from django.urls import reverse

from .origin import indexing_enabled, public_origin

PUBLIC_ROUTES = {'shop:home', 'catalog:list', 'catalog:brands', 'catalog:detail',
                 'support:contact', 'support:help', 'support:impressum',
                 'support:datenschutz', 'support:agb', 'support:widerruf', 'support:versand_zahlung'}
PAGINATED_ROUTES = {'catalog:list', 'catalog:brands'}


class PagePolicy:
    """Conservative URL policy: only named public pages can become indexable."""

    def __init__(self, request, context=None, *, status=200):
        context = context or {}
        match = getattr(request, 'resolver_match', None)
        self.route = match.view_name if match else ''
        self.language = getattr(request, 'LANGUAGE_CODE', 'de')
        self.is_public = self.route in PUBLIC_ROUTES and status == 200
        self.has_query = bool(request.GET)
        clean_page = (self.route in PAGINATED_ROUTES and set(request.GET) == {'page'}
                      and len(request.GET.getlist('page')) == 1
                      and request.GET['page'].isascii() and request.GET['page'].isdigit()
                      and len(request.GET['page']) <= 8 and int(request.GET['page']) >= 1)
        self.page = 1
        if clean_page:
            self.page = context.get('catalog_listing', {}).get('page', 1)
            if context.get('brand_page'):
                self.page = context['brand_page'].number
        # The current storefront explicitly presents demo stock/prices. Publication
        # must not turn illustrative PDPs into indexable commercial offers.
        demo = self.route == 'catalog:detail' and not context.get('seo_product_published', False)
        self.indexable = (indexing_enabled() and self.is_public and self.language == 'de'
                          and (not self.has_query or clean_page) and not demo)
        self.robots = 'index, follow' if self.indexable else 'noindex, nofollow'
        self.canonical = ''
        if self.is_public and public_origin():
            kwargs = match.kwargs if self.route == 'catalog:detail' else None
            path = reverse(self.route, kwargs=kwargs)
            if clean_page and self.page > 1:
                path += '?' + urlencode({'page': self.page})
            self.canonical = public_origin() + path
