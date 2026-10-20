import re
from decimal import Decimal

import pytest
from django.urls import reverse

from web.orders.models import Order, OrderLine

pytestmark = pytest.mark.django_db


def test_customer_history_is_owned_bounded_and_snapshot_backed(client, django_user_model):
    owner = django_user_model.objects.create_user(username='order-owner')
    other = django_user_model.objects.create_user(username='other-owner')
    own = Order.objects.create(user=owner, total_amount=Decimal('18.75'), is_test=True,
                               address={'first_name': '<script>unsafe</script>', 'street': 'Testweg 1'})
    foreign = Order.objects.create(user=other, total_amount=Decimal('999.00'), is_test=True)
    OrderLine.objects.create(order=own, sku='SNAPSHOT-1', product_name='Saved <model>',
                             quantity=1, unit_amount=Decimal('18.75'))
    client.force_login(owner)
    history = client.get(reverse('customer:orders'))
    assert history.status_code == 200
    assert str(own.reference) in history.content.decode()
    assert str(foreign.reference) not in history.content.decode()
    detail = client.get(reverse('customer:order_receipt', kwargs={'reference': own.reference}))
    assert detail.status_code == 200
    assert detail['Cache-Control'] == 'no-store, private'
    assert 'Saved &lt;model&gt;' in detail.content.decode()
    assert '&lt;script&gt;unsafe&lt;/script&gt;' in detail.content.decode()
    assert '003404342893829104' not in detail.content.decode()
    assert client.get(reverse('customer:order_receipt', kwargs={'reference': foreign.reference})).status_code == 404
    assert client.get(reverse('customer:order_detail')).url == reverse('customer:orders')


def test_customer_history_requires_login_and_no_fake_latest_order(client, django_user_model):
    user = django_user_model.objects.create_user(username='empty-order-owner')
    response = client.get(reverse('customer:orders'))
    assert response.status_code == 302
    assert reverse('account_login') in response.url
    client.force_login(user)
    before = Order.objects.count()
    response = client.get(reverse('customer:overview'))
    assert response.context['customer_latest_order'] is None
    assert response.context['customer_order_count'] == 0
    visible = re.sub(r'<script\b[^>]*>.*?</script>', '', response.content.decode(), flags=re.S)
    assert 'MM-849204' not in visible
    assert Order.objects.count() == before
