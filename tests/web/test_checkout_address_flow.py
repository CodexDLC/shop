import pytest
from django.core.management import call_command
from django.urls import reverse

from tests.web.test_checkout_addresses import BILLING, HOME
from tests.web.test_local_commerce import add
from web.catalog.models import ProductVariant
from web.orders.models import Order

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('station', [False, True])
def test_addresses_survive_review_order_and_confirmation(client, station):
    call_command('seed_demo_catalog')
    variant = ProductVariant.objects.filter(is_active=True, demo_quantity__gte=3).first()
    add(client, variant)
    payload = HOME | BILLING
    if station:
        payload |= {'shipping_type': 'packstation', 'street': '', 'post_number': '12345678',
                    'packstation_number': '123'}
    assert client.post(reverse('orders:address'), payload).status_code == 302
    review = client.get(reverse('payments:review'))
    assert review.status_code == 200
    assert review.context['checkout_billing_address']['street'] == BILLING['billing_street']
    if station:
        assert b'12345678' in review.content
    token = review.context['checkout_token']
    result = client.post(reverse('payments:review'), {'method': 'test', 'checkout_token': token})
    assert result.status_code == 302
    order = Order.objects.get()
    assert order.billing_address['street'] == BILLING['billing_street']
    assert order.address['street'] == ('Packstation 123' if station else HOME['street'])
    html = client.get(result.url).content.decode()
    assert BILLING['billing_street'] in html
    if station:
        assert '12345678' in html
    assert client.post(reverse('payments:review'), {'method': 'test', 'checkout_token': token}).url == result.url
    assert Order.objects.count() == 1


def test_changed_billing_address_invalidates_review(client):
    call_command('seed_demo_catalog')
    add(client, ProductVariant.objects.filter(is_active=True, demo_quantity__gte=3).first())
    client.post(reverse('orders:address'), HOME | BILLING)
    token = client.get(reverse('payments:review')).context['checkout_token']
    client.post(reverse('orders:address'), HOME | BILLING | {'billing_city': 'Hamburg'})
    assert client.post(reverse('payments:review'), {'method': 'test', 'checkout_token': token}).status_code == 409
    assert not Order.objects.exists()
