import asyncio
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from codex_ecommerce.inventory import OperationContext
from web.catalog.models import Brand, Category, Product, ProductVariant
from web.inventory import services
from web.inventory.models import ReservationLine, StockBalance
from workers.tasks.inventory_expiry import inventory_expiry


@pytest.mark.django_db(transaction=True)
def test_worker_to_django_expiry_in_disposable_database(live_server, settings, monkeypatch):
    token = 'x' * 32
    actor = get_user_model().objects.create_user(username='expiry-integration', is_staff=True, is_superuser=True)
    brand = Brand.objects.create(slug='expiry-brand', name='Expiry')
    category = Category.objects.create(slug='expiry-category', name_key='expiry')
    product = Product.objects.create(slug='expiry-product', model_name='Expiry', brand=brand, category=category)
    variant = ProductVariant.objects.create(product=product, sku='EXPIRY-HTTP', color_code='black',
        color_name_key='black', size='M', price='10.00')
    def context(key, revision):
        return OperationContext(key, 'staff', str(actor.pk), 'HTTP expiry test', revision)
    services.initialize(actor=actor, variant_id=variant.pk, quantity=8, context=context('init-http', 0))
    now = timezone.now()
    services.reserve(actor=actor, variant_id=variant.pk, reservation_id='http-line', quantity=5,
        context=context('hold-http', 1), expires_at=now - timedelta(minutes=1), now=now - timedelta(minutes=2))
    settings.INVENTORY_EXPIRY_ENABLED = True
    settings.INVENTORY_EXPIRY_TOKEN = token
    settings.INVENTORY_EXPIRY_ACTOR_ID = actor.pk
    settings.INVENTORY_EXPIRY_BATCH_SIZE = 100
    monkeypatch.setenv('INVENTORY_EXPIRY_ENABLED', '1')
    monkeypatch.setenv('INVENTORY_EXPIRY_URL', live_server.url + '/internal/inventory/expiry/')
    monkeypatch.setenv('INVENTORY_EXPIRY_TOKEN', token)
    result = asyncio.run(inventory_expiry({}))
    assert result == {'scanned': 1, 'expired': 1, 'skipped': 0, 'has_more': False}
    assert ReservationLine.objects.get(pk='http-line').state == 'closed'
    assert StockBalance.objects.get(variant=variant).reserved == 0
