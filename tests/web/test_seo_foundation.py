import json
import re
from xml.etree import ElementTree

import pytest
from django.core.management import call_command
from django.test import Client, override_settings
from django.utils import timezone

from web.catalog.models import Product, ProductReview

pytestmark = pytest.mark.django_db


@pytest.fixture
def catalog():
    call_command('seed_demo_catalog')
    return Product.objects.get(slug='manstore-m2223')


def head(response):
    return response.content.decode().split('</head>')[0]


def canonical(response):
    match = re.search(r'<link rel="canonical" href="([^"]+)"', head(response))
    return match.group(1) if match else ''


@override_settings(SEO_PUBLIC_ORIGIN='https://store.example.com', SEO_INDEXING_ENABLED=True)
def test_public_head_is_unique_host_safe_and_has_no_query_leaks(catalog):
    response = Client().get('/katalog/?q=personal-secret&color=black', HTTP_HOST='localhost')
    html = head(response)
    assert html.count('<title>') == 1
    assert html.count('name="description"') == 1
    assert html.count('rel="canonical"') == 1
    assert canonical(response) == 'https://store.example.com/katalog/'
    assert 'personal-secret' not in html
    assert 'noindex, nofollow' in html
    assert 'noindex' in response['X-Robots-Tag']
    assert 'property="og:title"' in html


def test_default_blocking_robots_and_empty_sitemap(catalog):
    response = Client().get('/')
    assert 'noindex, nofollow' in head(response)
    assert 'noindex' in response['X-Robots-Tag']
    assert 'Disallow: /' in Client().get('/robots.txt').content.decode()
    assert list(ElementTree.fromstring(Client().get('/sitemap.xml').content)) == []


@pytest.mark.parametrize('origin', ['', 'http://store.example.com', 'https://localhost',
                                    'https://127.0.0.1', 'https://user:pass@store.example.com',
                                    'https://store.example.com/path', 'https://store.example.com?token=secret',
                                    'https://store.example.com/#fragment', '//store.example.com',
                                    'https://store.example.com:444', 'https://store.example.com\\@evil.com'])
@override_settings(SEO_INDEXING_ENABLED=True)
def test_invalid_origins_fail_closed(origin, catalog):
    with override_settings(SEO_PUBLIC_ORIGIN=origin):
        response = Client().get('/')
        assert not canonical(response)
        assert 'noindex' in response['X-Robots-Tag']
        assert 'Disallow: /' in Client().get('/robots.txt').content.decode()


@override_settings(SEO_INDEXING_ENABLED=True, SEO_PUBLIC_ORIGIN='https://store.example.com', SEO_FORCE_NOINDEX=True)
def test_staging_cannot_be_opened_by_public_flag(catalog):
    assert 'noindex' in Client().get('/')['X-Robots-Tag']
    assert 'Disallow: /' in Client().get('/robots.txt').content.decode()
    assert list(ElementTree.fromstring(Client().get('/sitemap.xml').content)) == []


@override_settings(SEO_INDEXING_ENABLED=True, SEO_PUBLIC_ORIGIN='https://store.example.com')
@pytest.mark.parametrize('path', ['/katalog/suche/', '/katalog/mobil/', '/katalog/leer/',
                                  '/accounts/login/', '/warenkorb/', '/vorschau/404/', '/missing/',
                                  '/produkt/manstore-m2223/variante/'])
def test_utility_alias_error_routes_always_noindex(path, catalog):
    response = Client().get(path)
    assert 'noindex' in response['X-Robots-Tag']
    assert not canonical(response)


@override_settings(SEO_INDEXING_ENABLED=True, SEO_PUBLIC_ORIGIN='https://store.example.com')
def test_pagination_uses_rendered_page_and_only_clean_page_queries(catalog):
    for index in range(14):
        clone = Product.objects.create(slug=f'item-{index}', model_name=f'Model {index}',
                                       brand=catalog.brand, category=catalog.category)
        row = catalog.variants.first()
        row.pk = None
        row.product = clone
        row.sku = f'REAL-{index}'
        row.save()
    response = Client().get('/katalog/?page=2')
    assert canonical(response) == 'https://store.example.com/katalog/?page=2'
    assert 'index, follow' in head(response)
    assert canonical(Client().get('/katalog/?page=999')) == 'https://store.example.com/katalog/?page=2'
    assert canonical(Client().get('/katalog/?page=bogus')) == 'https://store.example.com/katalog/'
    assert 'noindex' in Client().get('/katalog/?page=bogus')['X-Robots-Tag']
    assert canonical(Client().get('/katalog/?page=2&sort=price_asc')) == 'https://store.example.com/katalog/'


@override_settings(SEO_INDEXING_ENABLED=True, SEO_PUBLIC_ORIGIN='https://store.example.com')
def test_product_jsonld_uses_visible_reviews_and_script_safe_text_without_demo_offers(catalog):
    catalog.model_name = '</script><script>alert("x")</script>'
    catalog.save(update_fields=['model_name'])
    ProductReview.objects.create(product=catalog, rating=5, status='approved')
    ProductReview.objects.create(product=catalog, rating=1, status='pending')
    response = Client().get(f'/produkt/{catalog.slug}/?sku=secret')
    html = head(response)
    assert '<script>alert(' not in html
    schemas = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    graph = json.loads(schemas[0])['@graph']
    product = next(row for row in graph if row['@type'] == 'Product')
    assert product['name'] == f'{catalog.brand.name} {catalog.model_name}'
    assert product['aggregateRating']['reviewCount'] == 1
    assert product['aggregateRating']['ratingValue'] == 5
    assert 'offers' not in product
    assert product['url'] == f'https://store.example.com/produkt/{catalog.slug}/'
    assert any(row['@type'] == 'BreadcrumbList' for row in graph)
    assert 'noindex' in response['X-Robots-Tag']


@override_settings(SEO_INDEXING_ENABLED=True, SEO_PUBLIC_ORIGIN='https://store.example.com')
def test_product_without_reviews_omits_rating_and_rejects_unsafe_image(catalog):
    catalog.images.update(image_url='javascript:alert(1)')
    html = head(Client().get(f'/produkt/{catalog.slug}/'))
    assert 'aggregateRating' not in html
    assert 'javascript:' not in html


@override_settings(SEO_INDEXING_ENABLED=True, SEO_PUBLIC_ORIGIN='https://store.example.com')
def test_sitemap_only_published_active_non_demo_products_is_bounded(catalog, django_assert_max_num_queries):
    catalog.published_at = timezone.now()
    catalog.save(update_fields=['published_at'])
    real = Product.objects.create(slug='real-model', model_name='Real', brand=catalog.brand,
                                  category=catalog.category, published_at=timezone.now())
    row = catalog.variants.first()
    row.pk = None
    row.product = real
    row.sku = 'REAL-MODEL-M'
    row.save()
    with django_assert_max_num_queries(2):
        response = Client().get('/sitemap.xml')
    xml = response.content.decode()
    assert 'https://store.example.com/produkt/real-model/' in xml
    assert catalog.slug not in xml
    locations = ElementTree.fromstring(response.content).findall('{*}url/{*}loc')
    assert 'warenkorb' not in xml and '/ru/' not in xml
    assert all('?' not in location.text for location in locations)
    assert '<lastmod>' not in xml
    assert Client().get('/sitemap.xml?page=999').status_code == 404
    assert Client().get('/sitemap.xml?page=invalid').status_code == 404
    robots = Client().get('/robots.txt').content.decode()
    assert 'Sitemap: https://store.example.com/sitemap.xml' in robots


@override_settings(SEO_INDEXING_ENABLED=True, SEO_PUBLIC_ORIGIN='https://store.example.com')
def test_ru_fallback_not_advertised_as_published_translation(catalog):
    response = Client().get('/ru/katalog/')
    assert '<html lang="ru"' in response.content.decode()
    assert canonical(response) == 'https://store.example.com/ru/katalog/'
    assert 'hreflang=' not in head(response)
    assert 'noindex' in response['X-Robots-Tag']


@override_settings(SEO_INDEXING_ENABLED=True, SEO_PUBLIC_ORIGIN='https://store.example.com')
def test_sitemap_index_discovers_all_bounded_pages(catalog, monkeypatch):
    from web.seo import views

    monkeypatch.setattr(views, 'SITEMAP_PAGE_SIZE', 1)
    for index in range(2):
        product = Product.objects.create(slug=f'published-{index}', model_name=f'Published {index}',
                                         brand=catalog.brand, category=catalog.category, published_at=timezone.now())
        row = catalog.variants.first()
        row.pk = None
        row.product = product
        row.sku = f'PUBLISHED-{index}'
        row.save()
    response = Client().get('/sitemap.xml')
    tree = ElementTree.fromstring(response.content)
    assert tree.tag.endswith('sitemapindex')
    links = [node.text for node in tree.findall('{*}sitemap/{*}loc')]
    assert links == ['https://store.example.com/sitemap.xml?page=1',
                     'https://store.example.com/sitemap.xml?page=2']
    assert 'published-0' in Client().get('/sitemap.xml?page=1').content.decode()
    assert 'published-1' in Client().get('/sitemap.xml?page=2').content.decode()
    assert 'index, follow' in Client().get('/produkt/published-0/')['X-Robots-Tag']


@override_settings(SEO_INDEXING_ENABLED=True, SEO_PUBLIC_ORIGIN='https://store.example.com')
@pytest.mark.parametrize('marker', ['unpublished', 'future', 'inactive', 'demo_tag', 'demo_description', 'demo_sku'])
def test_each_publication_and_demo_gate_excludes_product(catalog, marker):
    from datetime import timedelta

    product = Product.objects.create(slug='not-public', model_name='Model', brand=catalog.brand,
                                     category=catalog.category, published_at=timezone.now())
    row = catalog.variants.first()
    row.pk = None
    row.product = product
    row.sku = 'ACTUAL-ONE'
    row.save()
    if marker == 'unpublished':
        product.published_at = None
    elif marker == 'future':
        product.published_at = timezone.now() + timedelta(days=1)
    elif marker == 'inactive':
        product.is_active = False
    elif marker == 'demo_tag':
        product.tags.add(catalog.tags.get(slug='demo'))
    elif marker == 'demo_description':
        product.description_key = 'catalog.product.demo_description'
    elif marker == 'demo_sku':
        row.sku = 'DEMO-ONE'
        row.save()
    product.save()
    assert '/produkt/not-public/' not in Client().get('/sitemap.xml').content.decode()
    assert 'noindex' in Client().get('/produkt/not-public/')['X-Robots-Tag']


def test_metadata_reuses_prefetched_product_snapshot_without_queries(catalog, django_assert_num_queries):
    from django.test import RequestFactory
    from django.urls import resolve

    from web.catalog.selectors import storefront_products
    from web.seo.metadata import page_metadata
    from web.seo.sitemap_products import product_is_published

    product = storefront_products().get(pk=catalog.pk)
    request = RequestFactory().get(f'/produkt/{product.slug}/')
    request.resolver_match = resolve(request.path)
    request.LANGUAGE_CODE = 'de'
    with django_assert_num_queries(0):
        published = product_is_published(product)
        page_metadata(request, {'seo_product_published': published, 'product': {
            'brand': product.brand.name, 'name': product.model_name,
        }})


@override_settings(SEO_PUBLIC_ORIGIN='https://store.example.com')
def test_root_blocks_can_be_overridden_and_child_titles_do_not_duplicate(catalog):
    from django.template import engines
    from django.test import RequestFactory

    template = engines['django'].from_string(
        "{% extends 'base.html' %}{% block title %}Custom title{% endblock %}"
        "{% block meta_description %}Custom description{% endblock %}"
        "{% block canonical %}<link rel=\"canonical\" href=\"https://store.example.com/custom/\">{% endblock %}"
        "{% block extra_head_schema %}<script type=\"application/ld+json\">{}</script>{% endblock %}")
    from django.contrib.auth.models import AnonymousUser

    request = RequestFactory().get('/')
    request.user = AnonymousUser()
    html = template.render({}, request=request).split('</head>')[0]
    assert html.count('<title>') == 1 and '<title>Custom title</title>' in html
    assert html.count('name="description"') == 1 and 'Custom description' in html
    assert html.count('rel="canonical"') == 1
    for path in ['/', '/katalog/', '/marken/', f'/produkt/{catalog.slug}/', '/service/',
                 '/rechtliches/impressum/', '/accounts/login/', '/warenkorb/']:
        html = head(Client().get(path))
        assert html.count('<title>') == 1, path
        assert html.count('name="description"') == 1, path
        assert '[' not in re.search(r'<title>(.*?)</title>', html, re.S).group(1)


@override_settings(SEO_INDEXING_ENABLED=True, SEO_PUBLIC_ORIGIN='https://store.example.com')
def test_response_preserves_preexisting_stricter_robot_directives():
    from django.http import HttpResponse
    from django.test import RequestFactory
    from django.urls import resolve

    from web.seo.middleware import SeoMiddleware

    request = RequestFactory().get('/')
    request.resolver_match = resolve('/')
    response = HttpResponse()
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    response = SeoMiddleware(lambda request: response)(request)
    assert response['X-Robots-Tag'] == 'noindex, nofollow, noarchive'


@override_settings(SEO_INDEXING_ENABLED=True, SEO_PUBLIC_ORIGIN='https://store.example.com')
def test_legal_hub_alias_is_noindex(catalog):
    response = Client().get('/rechtliches/')
    assert 'noindex' in response['X-Robots-Tag']
    assert not canonical(response)


def test_existing_json_noindex_is_preserved_and_unprotected_json_is_blocked():
    from django.http import JsonResponse
    from django.test import RequestFactory

    from web.seo.middleware import SeoMiddleware

    request = RequestFactory().get('/private-api/')
    response = JsonResponse({})
    response['X-Robots-Tag'] = 'noindex'
    assert SeoMiddleware(lambda request: response)(request)['X-Robots-Tag'] == 'noindex'
    response = JsonResponse({})
    assert SeoMiddleware(lambda request: response)(request)['X-Robots-Tag'] == 'noindex, nofollow'
