import json
import re
from pathlib import Path

import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django.utils.translation import override

from web.storefront.pages import page_manifest

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('page', page_manifest(), ids=lambda page: page['source'])
def test_reference_pages_render_as_namespaced_django_templates(page):
    if page['feature'] in {'shop', 'cart', 'orders', 'payments'} or page['name'] == 'product':
        call_command('seed_demo_catalog')
    client = Client()
    if page['feature'] == 'customer' and page['source'] not in {
        'auth.html', 'auth-mobile.html', 'register.html', 'register-mobile.html',
        'password-reset.html',
    }:
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_user(username='reference-preview')
        client.force_login(user)
    url = reverse(f"{page['feature']}:{page['name']}")
    if page['feature'] in {'orders', 'payments'} or page['source'] == 'cart.html':
        from web.catalog.models import ProductVariant
        variant = ProductVariant.objects.filter(is_active=True, demo_quantity__gt=0).first()
        client.post(reverse('cart:add'), {'sku': variant.sku, 'quantity': 1})
        client.post(reverse('orders:address'), {'email': 'preview@example.test', 'first_name': 'Max',
                    'last_name': 'Muster', 'street': 'Testweg 1', 'postal_code': '10115',
                    'city': 'Berlin', 'country': 'DE'})
        if page['name'] == 'confirmation':
            review = client.get(reverse('payments:review'))
            url = client.post(reverse('payments:review'), {'method': 'test',
                'checkout_token': review.context['checkout_token']}).url
    if page['source'] == 'account-order-detail.html':
        from web.orders.models import Order
        receipt = Order.objects.create(user=user, total_amount='0.00', is_test=True)
        url = reverse('customer:order_receipt', kwargs={'reference': receipt.reference})
    response = client.get(url, follow=True)
    assert response.status_code == 200
    html = response.content.decode()
    if page['feature'] == 'customer' and page['source'] in {
        'auth.html', 'auth-mobile.html', 'register.html', 'register-mobile.html',
        'password-reset.html',
    }:
        assert 'data-real-auth="true"' in html
        assert 'AtelierKuratierung2025' not in html
        return
    assert '{% ' not in html
    if page['source'] == 'account-mobile.html':
        assert 'data-customer-reference' in html
    else:
        source = {'legal-mobile.html': 'legal.html', 'checkout-address-errors.html': 'checkout-address.html'}.get(
            page['source'], page['source'])
        assert 'data-demo-page="' + source + '"' in html
    assert 'id="shop-routes"' in html
    assert 'Designvorschau' in html
    assert 'src="assets/' not in html
    assert '.js%3F' not in html
    assert response.context['demo_mode'] is True
    assert response.context['payment']['can_charge'] is False


@pytest.mark.django_db
def test_demo_requests_do_not_write_financial_or_customer_data(django_assert_num_queries):
    client = Client(enforce_csrf_checks=True)
    with django_assert_num_queries(0):
        assert client.get(reverse('payments:review')).status_code == 302
    assert client.post(reverse('payments:review'), {'amount': '1.00'}).status_code == 403
    assert Client().post(reverse('payments:review')).status_code == 400


def test_routes_and_source_fallback_are_language_aware():
    with override('ru'):
        assert reverse('catalog:list') == '/ru/katalog/'
    response = Client().get('/ru/katalog/')
    assert response.status_code == 200
    assert '<html lang="ru"' in response.content.decode()
    assert 'Unterwäsche' in response.content.decode()


def test_mock_values_are_rendered_from_context():
    call_command('seed_demo_catalog')
    response = Client().get(reverse('cart:detail'))
    assert response.context['cart']['total'] == sum(
        row['line_amount'] for row in response.context['cart']['lines']
    )
    assert response.context['cart']['lines'] == []
    assert response.context['cart']['total'] == 0
    visible = re.sub(r'<script\b[^>]*>.*?</script>', '', response.content.decode(), flags=re.S)
    assert '139,80' not in visible
    html = Client().get(reverse('shop:home')).content.decode()
    assert 'M2223 Bungee Pants' in html


def test_template_keys_exist_in_german_source_catalog():
    import re

    root = Path(__file__).resolve().parents[2] / 'src/web'
    messages = json.loads((root / 'localization/messages/de.json').read_text(encoding='utf-8'))
    for page in page_manifest():
        template = root / page['feature'] / 'templates' / page['template']
        for key in re.findall(r"{% text '([^']+)'", template.read_text(encoding='utf-8')):
            assert key in messages
