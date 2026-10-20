import re
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from web.catalog.models import ProductVariant
from web.orders.models import Order
from web.payments.models import PaymentAttempt

pytestmark = pytest.mark.django_db


@pytest.fixture
def variant():
    call_command('seed_demo_catalog')
    return ProductVariant.objects.filter(is_active=True, demo_quantity__gte=3, currency='EUR').first()


def add(client, variant, quantity=1):
    return client.post(reverse('cart:add'), {'sku': variant.sku, 'quantity': quantity, 'price': '0.01'})


def address(client):
    return client.post(reverse('orders:address'), {
        'email': 'guest@example.test', 'first_name': 'Max', 'last_name': 'Muster',
        'street': 'Musterstraße 12', 'postal_code': '10115', 'city': 'Berlin', 'country': 'DE',
    })


def test_cart_is_real_server_priced_and_isolated(client, variant):
    assert client.get(reverse('cart:detail')).context['cart']['lines'] == []
    assert add(client, variant, 2).status_code == 302
    cart = client.get(reverse('cart:detail')).context['cart']
    assert cart['total'] == variant.price * 2
    assert cart['lines'][0]['sku'] == variant.sku
    assert Client().get(reverse('cart:detail')).context['cart']['lines'] == []
    assert client.post(reverse('cart:update'), {'sku': variant.sku, 'quantity': 1}).status_code == 302
    assert client.post(reverse('cart:remove'), {'sku': variant.sku}).status_code == 302
    assert client.get(reverse('cart:detail')).context['cart']['lines'] == []


@pytest.mark.parametrize('quantity', ['0', '-1', '1.5', '21', 'abc', '999999999999999999999'])
def test_bad_quantity_is_rejected_without_cart_change(client, variant, quantity):
    assert add(client, variant, quantity).status_code == 400
    assert client.get(reverse('cart:detail')).context['cart']['lines'] == []


def test_bad_and_inactive_sku_and_mutating_get_rejected(client, variant):
    assert client.post(reverse('cart:add'), {'sku': 'missing', 'quantity': 1}).status_code == 400
    for route in ('add', 'update', 'remove'):
        assert client.get(reverse('cart:' + route)).status_code == 405
    variant.is_active = False
    variant.save()
    assert add(client, variant).status_code == 400


def test_csrf_is_required(variant):
    strict = Client(enforce_csrf_checks=True)
    assert add(strict, variant).status_code == 403


def test_checkout_snapshots_idempotency_ownership_no_payment_or_stock_write(client, variant):
    add(client, variant, 2)
    assert address(client).status_code == 302
    review = client.get(reverse('payments:review'))
    token = review.context['checkout_token']
    assert Order.objects.count() == PaymentAttempt.objects.count() == 0
    result = client.post(reverse('payments:review'), {'checkout_token': token, 'method': 'test', 'total': '0.01'})
    assert result.status_code == 302
    order = Order.objects.get()
    assert order.is_test and order.total_amount == variant.price * 2
    assert order.address['postal_code'] == '10115'
    assert order.lines.get().unit_amount == variant.price
    assert client.post(reverse('payments:review'), {'checkout_token': token, 'method': 'test'}).url == result.url
    assert Order.objects.count() == 1
    assert Client().get(result.url).status_code == 404
    assert client.get(result.url).status_code == 200
    assert client.get(reverse('cart:detail')).context['cart']['lines'] == []
    variant.refresh_from_db()
    assert variant.demo_quantity >= 3
    assert PaymentAttempt.objects.count() == 0
    ProductVariant.objects.filter(pk=variant.pk).update(price=Decimal('999.00'))
    assert order.lines.get().unit_amount != Decimal('999.00')


def test_stale_review_requires_review_again(client, variant):
    add(client, variant)
    address(client)
    token = client.get(reverse('payments:review')).context['checkout_token']
    ProductVariant.objects.filter(pk=variant.pk).update(price=variant.price + Decimal('1.00'))
    response = client.post(reverse('payments:review'), {'checkout_token': token, 'method': 'test'})
    assert response.status_code == 409
    assert Order.objects.count() == 0
    assert response.context['checkout_token'] != token


@pytest.mark.parametrize('changed', [{'country': 'AT'}, {'postal_code': '12A45'}, {'first_name': ''}])
def test_address_validation(client, variant, changed):
    add(client, variant)
    payload = {'email': 'guest@example.test', 'first_name': 'Max', 'last_name': 'Muster',
               'street': 'Musterstraße 12', 'postal_code': '10115', 'city': 'Berlin', 'country': 'DE'}
    response = client.post(reverse('orders:address'), payload | changed)
    assert response.status_code == 400
    assert response.context['address_form'].errors
    assert not Order.objects.exists()


def test_authenticated_order_ownership_and_cart_partition(client, variant, django_user_model):
    add(client, variant)
    owner = django_user_model.objects.create_user(username='local-owner')
    other = django_user_model.objects.create_user(username='local-other')
    client.force_login(owner)
    assert client.get(reverse('cart:detail')).context['cart']['lines'] == []
    add(client, variant)
    address(client)
    token = client.get(reverse('payments:review')).context['checkout_token']
    result = client.post(reverse('payments:review'), {'checkout_token': token, 'method': 'test'})
    assert Order.objects.get().user == owner
    assert client.get(result.url).status_code == 200
    another = Client()
    another.force_login(other)
    assert another.get(result.url).status_code == 404
    assert another.post(reverse('payments:review'), {'checkout_token': token, 'method': 'test'}).status_code == 409
    assert Order.objects.count() == 1


def test_malformed_reference_is_404(client):
    assert client.get(reverse('orders:confirmation') + '?reference=not-a-uuid').status_code == 404


def test_empty_checkout_redirects_and_get_never_creates_order(client):
    for name in ('orders:address', 'payments:review'):
        assert client.get(reverse(name)).url == reverse('cart:detail')
    assert client.get(reverse('orders:confirmation')).status_code == 404
    assert Order.objects.count() == PaymentAttempt.objects.count() == 0


def test_no_payment_method_or_no_token_cannot_create_order(client, variant):
    add(client, variant)
    address(client)
    token = client.get(reverse('payments:review')).context['checkout_token']
    assert client.post(reverse('payments:review'), {'checkout_token': token, 'method': 'paypal'}).status_code == 400
    assert client.post(reverse('payments:review'), {'method': 'test'}).status_code == 409
    assert not Order.objects.exists()


def test_stock_change_and_other_currency_are_rejected(client, variant):
    add(client, variant, 2)
    address(client)
    token = client.get(reverse('payments:review')).context['checkout_token']
    ProductVariant.objects.filter(pk=variant.pk).update(demo_quantity=1)
    assert client.post(reverse('payments:review'), {'checkout_token': token, 'method': 'test'}).status_code == 409
    assert not Order.objects.exists()
    client.post(reverse('cart:remove'), {'sku': variant.sku})
    ProductVariant.objects.filter(pk=variant.pk).update(demo_quantity=10, currency='USD')
    assert add(client, variant).status_code == 400


def test_invalid_post_does_not_render_fake_saved_address(client, variant):
    add(client, variant)
    result = client.post(reverse('orders:address'), {'email': 'not-an-email', 'country': 'DE'})
    html = result.content.decode()
    assert result.status_code == 400
    assert 'value="not-an-email"' in html
    assert 'Alexander' not in html
    assert 'aria-invalid="true"' in html


def test_confirmation_and_review_do_not_claim_real_payment_or_tracking(client, variant):
    add(client, variant)
    address(client)
    review = client.get(reverse('payments:review'))
    assert '256-Bit' not in re.sub(r'<script\b[^>]*>.*?</script>', '', review.content.decode(), flags=re.S)
    token = review.context['checkout_token']
    result = client.post(reverse('payments:review'), {'checkout_token': token, 'method': 'test'})
    html = re.sub(r'<script\b[^>]*>.*?</script>', '', client.get(result.url).content.decode(), flags=re.S)
    assert 'Transaktion autorisiert' not in html
    assert 'MM-849204' not in html
    assert 'JJD01' not in html


def test_same_cart_can_be_ordered_again_in_same_second(client, variant, monkeypatch):
    monkeypatch.setattr('django.core.signing.time.time', lambda: 2000000000)
    urls = []
    for _ in range(2):
        add(client, variant)
        address(client)
        token = client.get(reverse('payments:review')).context['checkout_token']
        result = client.post(reverse('payments:review'), {'checkout_token': token, 'method': 'test'})
        assert result.status_code == 302
        urls.append(result.url)
    assert urls[0] != urls[1]
    assert Order.objects.count() == 2


def test_token_tampering_and_changed_cart_require_new_review(client, variant):
    add(client, variant)
    address(client)
    token = client.get(reverse('payments:review')).context['checkout_token']
    assert client.post(reverse('payments:review'), {'checkout_token': token + 'bad', 'method': 'test'}).status_code == 409
    client.post(reverse('cart:update'), {'sku': variant.sku, 'quantity': 2})
    assert client.post(reverse('payments:review'), {'checkout_token': token, 'method': 'test'}).status_code == 409
    assert not Order.objects.exists()


def test_no_network_or_delivery_actions_in_local_checkout(client, variant, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Local checkout must not send requests or messages')
    monkeypatch.setattr('socket.create_connection', forbidden)
    monkeypatch.setattr('django.core.mail.send_mail', forbidden)
    original_quantity = variant.demo_quantity
    add(client, variant)
    address(client)
    token = client.get(reverse('payments:review')).context['checkout_token']
    assert client.post(reverse('payments:review'), {'checkout_token': token, 'method': 'test'}).status_code == 302
    variant.refresh_from_db()
    assert variant.demo_quantity == original_quantity
    assert PaymentAttempt.objects.count() == 0


def test_two_review_tokens_for_same_intent_return_same_order(client, variant, monkeypatch):
    now = [2000000000]
    monkeypatch.setattr('django.core.signing.time.time', lambda: now[0])
    add(client, variant)
    address(client)
    token_one = client.get(reverse('payments:review')).context['checkout_token']
    now[0] += 2
    token_two = client.get(reverse('payments:review')).context['checkout_token']
    assert token_one != token_two
    first = client.post(reverse('payments:review'), {'checkout_token': token_one, 'method': 'test'})
    second = client.post(reverse('payments:review'), {'checkout_token': token_two, 'method': 'test'})
    assert first.status_code == second.status_code == 302
    assert first.url == second.url
    assert Order.objects.count() == 1


def test_unique_constraint_retry_returns_existing_without_clearing_new_cart(client, variant, monkeypatch):
    from django.db.models.query import QuerySet
    add(client, variant)
    address(client)
    token = client.get(reverse('payments:review')).context['checkout_token']
    first = client.post(reverse('payments:review'), {'checkout_token': token, 'method': 'test'})
    add(client, variant)
    original_first = QuerySet.first
    reads = [0]
    def miss_first_order_read(queryset):
        if queryset.model is Order and reads[0] == 0:
            reads[0] += 1
            return None
        return original_first(queryset)
    monkeypatch.setattr(QuerySet, 'first', miss_first_order_read)
    duplicate = client.post(reverse('payments:review'), {'checkout_token': token, 'method': 'test'})
    assert duplicate.status_code == 302 and duplicate.url == first.url
    assert reads[0] == 1
    assert Order.objects.count() == 1
    assert client.get(reverse('cart:detail')).context['cart']['item_count'] == 1


def test_checkout_intent_is_created_by_address_post_not_review_get(client, variant):
    add(client, variant)
    address(client)
    nonce = client.session.get('local_checkout_address_guest_nonce')
    assert nonce
    client.get(reverse('payments:review'))
    assert client.session['local_checkout_address_guest_nonce'] == nonce
