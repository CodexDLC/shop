import json
from urllib.parse import urlsplit

from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe

from web.localization import translate_text

from .origin import public_origin


def absolute_image(value):
    """Accept clean HTTPS images or configured-origin relative media paths."""
    if not isinstance(value, str) or not value or any(character.isspace() for character in value):
        return ''
    if '\\' in value:
        return ''
    if value.startswith('/') and not value.startswith('//'):
        return public_origin() + value if public_origin() else ''
    try:
        parsed = urlsplit(value)
        if (parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password
                and not parsed.query and not parsed.fragment):
            return value
    except ValueError:
        pass
    return ''


def product_schema(context, canonical):
    product = context.get('product', {})
    if not canonical or not product:
        return ''
    item = {'@type': 'Product', 'name': f"{product['brand']} {product['name']}",
            'url': canonical, 'brand': {'@type': 'Brand', 'name': product['brand']}}
    description = context.get('product_information', {}).get('description') or product.get('description', '')
    if description:
        item['description'] = strip_tags(description)
    image = absolute_image(product.get('photo_url', ''))
    if image:
        item['image'] = [image]
    article = context.get('manufacturer_article')
    if article:
        item['mpn'] = article
    summary = context.get('review_summary', {})
    if summary.get('count') and summary.get('average') is not None:
        average = float(summary['average'])
        if 1 <= average <= 5:
            item['aggregateRating'] = {'@type': 'AggregateRating', 'ratingValue': average,
                                       'reviewCount': summary['count'], 'bestRating': 5, 'worstRating': 1}
    # No offers until a real price/availability adapter replaces demo commerce.
    crumbs = {'@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': 1, 'name': translate_text('seo.home.title'),
         'item': public_origin() + reverse('shop:home')},
        {'@type': 'ListItem', 'position': 2, 'name': translate_text('catalog.listing.title'),
         'item': public_origin() + reverse('catalog:list')},
        {'@type': 'ListItem', 'position': 3, 'name': item['name'], 'item': canonical},
    ]}
    encoded = json.dumps({'@context': 'https://schema.org', '@graph': [item, crumbs]}, ensure_ascii=True)
    # Escaping JSON delimiters prevents closing a script element from catalog text.
    return mark_safe(encoded.translate(str.maketrans({'<': '\\u003C', '>': '\\u003E', '&': '\\u0026'})))
