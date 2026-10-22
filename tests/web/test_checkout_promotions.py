from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from tests.web.test_local_commerce import add, address
from web.cart.models import PromoCode
from web.catalog.models import ProductVariant
from web.orders.models import Order

pytestmark = pytest.mark.django_db


@pytest.fixture
def variant():
    call_command('seed_demo_catalog')
    return ProductVariant.objects.filter(is_active=True, demo_quantity__gte=3, currency='EUR').first()


def promo(**changes):
    return PromoCode.objects.create(code='SAVE', kind='percent', value=Decimal('10'), is_active=True, **changes)


def apply(client, code='SAVE'):
    return client.post(reverse('cart:coupon_apply'), {'code': code})


def cart(client):
    return client.get(reverse('cart:detail')).context['cart']


def test_apply_remove_replace_and_server_amount(client, variant):
    add(client, variant, 2)
    promo()
    assert apply(client, ' save ').status_code == 302
    result = cart(client)
    assert result['coupon_code'] == 'SAVE'
    assert result['subtotal'] == variant.price * 2
    assert result['total'] == result['subtotal'] - result['discount_amount']
    assert result['discount_amount'] > 0
    assert apply(client, 'missing').status_code == 400
    assert cart(client)['coupon_code'] == 'SAVE'
    PromoCode.objects.create(code='FIXED', kind='fixed', value=Decimal('999'), is_active=True)
    assert apply(client, 'fixed').status_code == 302
    assert cart(client)['total'] == 0
    assert client.post(reverse('cart:coupon_remove')).status_code == 302
    assert cart(client)['discount_amount'] == 0


@pytest.mark.parametrize('changes,error', [
    ({'is_active': False}, 'commerce.error.coupon_invalid'),
    ({'ends_at': timezone.now() - timedelta(seconds=1)}, 'commerce.error.coupon_expired'),
    ({'starts_at': timezone.now() + timedelta(days=1)}, 'commerce.error.coupon_invalid'),
    ({'min_subtotal': Decimal('9999')}, 'commerce.error.coupon_minimum'),
])
def test_selected_invalid_code_remains_removable(client, variant, changes, error):
    add(client, variant)
    rule = promo()
    apply(client)
    PromoCode.objects.filter(pk=rule.pk).update(**changes)
    result = cart(client)
    assert result['coupon_code'] == 'SAVE' and error in result['errors']
    assert not result['can_checkout']
    assert client.post(reverse('cart:coupon_remove')).status_code == 302
    assert cart(client)['can_checkout']


def test_coupon_isolation_csrf_and_get(client, variant, django_user_model):
    add(client, variant)
    promo()
    apply(client)
    assert cart(Client())['coupon_code'] == ''
    client.force_login(django_user_model.objects.create_user(username='coupon-owner'))
    assert cart(client)['coupon_code'] == ''
    for route in ('coupon_apply', 'coupon_remove'):
        assert client.get(reverse('cart:' + route)).status_code == 405
        assert Client(enforce_csrf_checks=True).post(reverse('cart:' + route), {'code': 'SAVE'}).status_code == 403


def test_snapshot_rule_changes_stale_and_idempotency(client, variant):
    add(client, variant)
    rule = promo()
    apply(client)
    address(client)
    token = client.get(reverse('payments:review')).context['checkout_token']
    # The result is unchanged, but the business rule changed and must be reviewed.
    PromoCode.objects.filter(pk=rule.pk).update(min_subtotal=Decimal('0.01'))
    assert client.post(reverse('payments:review'), {'checkout_token': token, 'method': 'test'}).status_code == 409
    assert not Order.objects.exists()
    token = client.get(reverse('payments:review')).context['checkout_token']
    result = client.post(reverse('payments:review'), {'checkout_token': token, 'method': 'test'})
    assert result.status_code == 302
    order = Order.objects.get()
    assert order.coupon_code == 'SAVE' and order.subtotal_amount == variant.price
    assert order.total_amount == order.subtotal_amount - order.discount_amount + order.shipping_amount
    assert order.billing_address['postal_code'] == '10115'
    assert cart(client)['coupon_code'] == ''
    assert client.post(reverse('payments:review'), {'checkout_token': token, 'method': 'test'}).url == result.url
    assert Order.objects.count() == 1


@pytest.mark.parametrize('changes', [
    {'code': 'bad space'}, {'code': 'ä'}, {'kind': 'percent', 'value': Decimal('101')},
    {'value': Decimal('0')}, {'min_subtotal': Decimal('-1')}, {'currency': 'USD'},
    {'starts_at': timezone.now(), 'ends_at': timezone.now() - timedelta(days=1)},
])
def test_promo_validation(changes):
    data = {'code': 'VALID', 'kind': 'fixed', 'value': Decimal('1')}
    rule = PromoCode(**(data | changes))
    with pytest.raises(ValidationError):
        rule.full_clean()


def test_database_guards_order_discount_and_promotion():
    with pytest.raises(IntegrityError), transaction.atomic():
        PromoCode.objects.create(code='BAD', kind='percent', value=101)
    with pytest.raises(IntegrityError), transaction.atomic():
        Order.objects.create(total_amount=8, subtotal_amount=10, discount_amount=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        Order.objects.create(total_amount=0, subtotal_amount=10, discount_amount=11)

def test_expired_code_can_be_replaced_and_line_quantity_repaired(client, variant):
    add(client, variant, 2)
    rule = promo()
    apply(client)
    PromoCode.objects.filter(pk=rule.pk).update(ends_at=timezone.now() - timedelta(seconds=1))
    assert client.post(reverse('cart:update'), {'sku': variant.sku, 'quantity': 1}).status_code == 302
    PromoCode.objects.create(code='NEW', kind='fixed', value=Decimal('1.00'), is_active=True)
    assert apply(client, 'new').status_code == 302
    assert cart(client)['coupon_code'] == 'NEW'


@pytest.mark.parametrize('mutation', ['amount', 'expired', 'removed', 'deleted'])
def test_changed_discount_cannot_create_old_order(client, variant, mutation):
    add(client, variant)
    rule = promo()
    apply(client)
    address(client)
    token = client.get(reverse('payments:review')).context['checkout_token']
    if mutation == 'amount':
        PromoCode.objects.filter(pk=rule.pk).update(value=Decimal('20.00'))
    elif mutation == 'expired':
        PromoCode.objects.filter(pk=rule.pk).update(ends_at=timezone.now() - timedelta(seconds=1))
    elif mutation == 'deleted':
        rule.delete()
    else:
        client.post(reverse('cart:coupon_remove'))
    response = client.post(reverse('payments:review'), {'checkout_token': token, 'method': 'test'})
    assert response.status_code == 409
    assert not Order.objects.exists()


def test_order_creation_locks_promotion_within_atomic(client, variant, monkeypatch):
    from django.db import connection
    from django.db.models.query import QuerySet

    add(client, variant)
    promo()
    apply(client)
    address(client)
    token = client.get(reverse('payments:review')).context['checkout_token']
    original_lock = QuerySet.select_for_update
    locks = []

    def observed_lock(queryset, *args, **kwargs):
        if queryset.model is PromoCode:
            locks.append(connection.in_atomic_block)
        return original_lock(queryset, *args, **kwargs)

    monkeypatch.setattr(QuerySet, 'select_for_update', observed_lock)
    response = client.post(reverse('payments:review'), {'checkout_token': token, 'method': 'test'})
    assert response.status_code == 302 and locks == [True]


def test_default_inactive_and_legacy_order_supported():
    assert not PromoCode.objects.create(code='OFF', kind='fixed', value=1).is_active
    legacy = Order.objects.create(total_amount=Decimal('12.00'))
    assert legacy.subtotal_amount is None and legacy.discount_amount == 0


def test_database_rejects_lowercase_or_invalid_code():
    for code in ('save', 'A\n', 'Ä', 'A' * 33):
        with pytest.raises(IntegrityError), transaction.atomic():
            PromoCode.objects.create(code=code, kind='fixed', value=1)

@pytest.mark.parametrize('subtotal,discount,total', [('10.05', '1.01', '9.04'), ('0.30', '0.10', '0.20')])
def test_decimal_cent_snapshots_satisfy_consistency_constraint(subtotal, discount, total):
    order = Order.objects.create(subtotal_amount=Decimal(subtotal), discount_amount=Decimal(discount),
                                 total_amount=Decimal(total))
    assert order.pk
