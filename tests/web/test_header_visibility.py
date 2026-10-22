from datetime import timedelta

import pytest
from django.core.management import call_command
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from web.catalog.models import Product, ProductVariant

pytestmark = pytest.mark.django_db


def header_hrefs():
    from tests.web.test_header_navigation import HeaderElements
    return [attrs['href'] for tag, attrs in HeaderElements(render_to_string('includes/header.html')).elements
            if tag == 'a']


def test_empty_sections_are_absent_in_both_menus():
    links = header_hrefs()
    for destination in ('?new=1', '?section=underwear', '?section=swimwear', '?sale=1'):
        assert reverse('catalog:list') + destination not in links
    assert reverse('catalog:brands') not in links
    assert reverse('catalog:list') + '#catalog-query' in links


def test_live_visibility_rechecks_dates_flags_and_categories_without_global_cache():
    assert reverse('catalog:brands') not in header_hrefs()
    call_command('seed_demo_catalog')
    product = Product.objects.first()
    links = header_hrefs()
    assert links.count(reverse('catalog:list') + '?section=underwear') == 2
    assert links.count(reverse('catalog:brands')) == 2
    assert reverse('catalog:list') + '?new=1' not in links
    assert reverse('catalog:list') + '?sale=1' not in links
    product.new_until = timezone.localdate()
    product.save(update_fields=['new_until'])
    product.category.section = 'swimwear'
    product.category.save(update_fields=['section'])
    ProductVariant.objects.filter(product=product).update(is_on_sale=True, demo_quantity=0)
    links = header_hrefs()
    for destination in ('?new=1', '?sale=1', '?section=swimwear'):
        assert links.count(reverse('catalog:list') + destination) == 2
    product.new_until = timezone.localdate() - timedelta(days=1)
    product.save(update_fields=['new_until'])
    assert reverse('catalog:list') + '?new=1' not in header_hrefs()


@pytest.mark.parametrize('product_active,variant_active,currency', [
    (False, True, 'EUR'), (True, False, 'EUR'), (True, True, 'USD'),
])
def test_unpublished_or_foreign_currency_does_not_enable_links(product_active, variant_active, currency):
    call_command('seed_demo_catalog')
    Product.objects.update(is_active=product_active, new_until=timezone.localdate())
    ProductVariant.objects.update(is_active=variant_active, currency=currency, is_on_sale=True)
    links = header_hrefs()
    assert reverse('catalog:brands') not in links
    assert reverse('catalog:list') + '?new=1' not in links
    assert reverse('catalog:list') + '?sale=1' not in links
    assert reverse('catalog:list') + '?section=underwear' not in links


def test_sale_requires_the_active_eur_variant():
    call_command('seed_demo_catalog')
    variant = ProductVariant.objects.first()
    variant.is_on_sale = True
    variant.currency = 'USD'
    variant.save(update_fields=['is_on_sale', 'currency'])
    assert reverse('catalog:brands') in header_hrefs()
    assert reverse('catalog:list') + '?sale=1' not in header_hrefs()


def test_header_visibility_is_one_bounded_query(django_assert_num_queries):
    call_command('seed_demo_catalog')
    with django_assert_num_queries(1):
        header_hrefs()
    product = Product.objects.first()
    for number in range(40):
        model = Product.objects.create(slug=f'nav-{number}', brand=product.brand, category=product.category,
                                       model_name=f'Navigation {number}')
        ProductVariant.objects.create(product=model, sku=f'NAV-{number}', color_code='black', size='M', price='5.00')
    with django_assert_num_queries(1):
        header_hrefs()


def test_auth_and_public_pages_use_the_same_visibility(client):
    call_command('seed_demo_catalog')
    for route in ('account_login', 'shop:home', 'support:impressum'):
        html = client.get(reverse(route)).content.decode().split('</header>', 1)[0]
        assert 'href="' + reverse('catalog:list') + '?section=swimwear"' not in html
        assert 'href="' + reverse('catalog:list') + '?section=underwear"' in html
