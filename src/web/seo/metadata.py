from django.utils.html import strip_tags

from web.localization import translate_text

from .display import display_title
from .policy import PagePolicy
from .structured_data import absolute_image, product_schema

TITLE_KEYS = {
    'shop:home': 'seo.home.title', 'catalog:list': 'catalog.listing.title',
    'catalog:brands': 'catalog.brands.title', 'support:help': 'seo.help.title',
    'support:contact': 'seo.contact.title',
}


def page_metadata(request, context=None, *, status=200):
    context = context or {}
    policy = PagePolicy(request, context, status=status)
    title = translate_text(TITLE_KEYS.get(policy.route, 'seo.utility.title'))
    description = translate_text('seo.default.description')
    product = context.get('product', {})
    if policy.route == 'catalog:detail' and product:
        title = f"{product['brand']} {product['name']}"
        description = (context.get('product_information', {}).get('description')
                       or product.get('description') or title)
    elif policy.route == 'catalog:list' and context.get('selected_category'):
        category = context['selected_category']
        title = category.seo_title or category.name
        description = category.seo_description or context.get('seo_visible_body') or category.description or title
    elif context.get('legal_document'):
        title = translate_text(context['legal_document'].title_key)
        description = title
    elif policy.route in TITLE_KEYS:
        description = translate_text('seo.' + policy.route.replace(':', '.') + '.description')
    overrides = context.get('seo_overrides', {})
    title = overrides.get('title', title)
    description = overrides.get('description', description)
    if policy.page > 1:
        title += ' · ' + translate_text('seo.page', page=policy.page)
    return {'title': display_title(title), 'description': strip_tags(description)[:300],
            'robots': policy.robots, 'canonical': policy.canonical,
            'og_type': 'product' if policy.route == 'catalog:detail' else 'website',
            'image': absolute_image(product.get('photo_url', '')) if policy.route == 'catalog:detail' else '',
            'schema': product_schema(context, policy.canonical) if policy.route == 'catalog:detail' else '',
            # No alternates: only DE has a complete published storefront.
            'hreflangs': ()}


def seo_context(request):
    return {'seo': page_metadata(request)}
