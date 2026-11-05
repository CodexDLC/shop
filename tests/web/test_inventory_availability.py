"""Shared read model exercised against isolated fixtures, never working stock."""
import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.http import QueryDict
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from codex_ecommerce.catalog import CatalogSelectionError
from codex_ecommerce.inventory import OperationContext
from web.catalog.adapters import CatalogVariantSelection
from web.catalog.listing_context import ListingContext
from web.catalog.listing_request import ListingRequest
from web.catalog.models import Brand, Category, Product, ProductVariant
from web.catalog.presentation import product_presentation
from web.catalog.recommendations import collection_suggestions
from web.catalog.selectors import storefront_products
from web.inventory import services
from web.inventory.models import InventoryMovement, ReservationLine, StockBalance

pytestmark = pytest.mark.django_db


@pytest.fixture
def inventory(settings):
    settings.SHOP_CHECKOUT_STOCK_MODE = 'inventory_test'
    actor = get_user_model().objects.create_superuser(username='availability', password='unused')
    brand = Brand.objects.create(slug='availability', name='Availability')
    category = Category.objects.create(slug='availability', name_key='Availability')
    product = Product.objects.create(slug='availability', model_name='Availability', brand=brand, category=category)
    variants = []
    for size, quantity in [('missing', None), ('zero', 0), ('reserved', 2), ('M', 3)]:
        variant = ProductVariant.objects.create(product=product, sku=f'AV-{size}', color_code='black',
            color_name_key='black', size=size, price=Decimal('10.00'), demo_quantity=90)
        if quantity is not None:
            services.initialize(actor=actor, variant_id=variant.pk, quantity=quantity,
                context=OperationContext(f'init-{size}', 'staff', str(actor.pk), 'Isolated availability QA', 0))
        variants.append(variant)
    now = timezone.now()
    services.reserve(actor=actor, variant_id=variants[2].pk, reservation_id='availability-held', quantity=2,
        expires_at=now + timedelta(minutes=10), now=now,
        context=OperationContext('hold', 'staff', str(actor.pk), 'Isolated availability QA', 1))
    return actor, product, variants


def listing(params=''):
    return ListingContext(ListingRequest.from_query(QueryDict(params))).build()


def test_projection_distinguishes_missing_zero_and_reserved_without_demo_fallback(inventory):
    from web.inventory.availability import InventoryAvailability
    from web.inventory.availability_queries import with_availability

    _, _, variants = inventory
    rows = list(with_availability(ProductVariant.objects.all()).order_by('pk'))
    snapshots = [InventoryAvailability.from_variant(row) for row in rows]
    assert [snapshot.quantity for snapshot in snapshots] == [None, 0, 0, 3]
    assert [snapshot.configured for snapshot in snapshots] == [False, True, True, True]
    assert [snapshot.available for snapshot in snapshots] == [False, False, False, True]
    assert [snapshot.mode for snapshot in snapshots] == ['inventory_test'] * 4
    # The read model never claims an inactive or unsupported currency SKU is sellable.
    ProductVariant.objects.filter(pk=variants[3].pk).update(is_active=False)
    assert not InventoryAvailability.from_variant(with_availability(ProductVariant.objects.all()).get(pk=variants[3].pk)).available
    ProductVariant.objects.filter(pk=variants[3].pk).update(is_active=True, currency='USD')
    assert not InventoryAvailability.from_variant(with_availability(ProductVariant.objects.all()).get(pk=variants[3].pk)).available


def test_demo_mode_is_explicit_and_does_not_query_inventory(inventory, settings, django_assert_num_queries):
    from web.inventory.availability import InventoryAvailability
    from web.inventory.availability_queries import with_availability

    settings.SHOP_CHECKOUT_STOCK_MODE = 'demo'
    with django_assert_num_queries(1) as captured:
        snapshots = [InventoryAvailability.from_variant(row) for row in with_availability(ProductVariant.objects.all())]
    assert all(row.quantity == 90 and row.available and row.mode == 'demo' for row in snapshots)
    assert all('inventory_stockbalance' not in row['sql'] for row in captured.captured_queries)


def test_inventory_projection_requires_explicit_loaded_snapshot(inventory, settings, django_assert_num_queries):
    from web.inventory.availability import InventoryAvailability
    from web.inventory.availability_queries import with_availability

    _, _, variants = inventory
    # No model property is allowed to silently cause an inventory lookup in a loop.
    with django_assert_num_queries(0), pytest.raises(ValueError, match='with_availability'):
        InventoryAvailability.from_variant(variants[3])
    settings.SHOP_CHECKOUT_STOCK_MODE = 'demo'
    demo_row = with_availability(ProductVariant.objects.all()).get(pk=variants[3].pk)
    settings.SHOP_CHECKOUT_STOCK_MODE = 'inventory_test'
    with django_assert_num_queries(0), pytest.raises(ValueError, match='with_availability'):
        InventoryAvailability.from_variant(demo_row)


def test_listing_and_sort_match_the_same_stocked_sale_size_color_price(inventory):
    actor, product, variants = inventory
    ProductVariant.objects.filter(pk=variants[3].pk).update(is_on_sale=True)
    blue = ProductVariant.objects.create(product=product, sku='BLUE-L', color_code='blue',
        color_name_key='blue', size='L', price=99, demo_quantity=100, is_on_sale=True)
    for params in ('color=blue&in_stock=1', 'size=zero&in_stock=1', 'size=reserved&in_stock=1',
                   'size=missing&in_stock=1', 'color=black&size=L&in_stock=1', 'min_price=90&in_stock=1'):
        assert listing(params)['total'] == 0
    services.initialize(actor=actor, variant_id=blue.pk, quantity=1,
        context=OperationContext('init-blue', 'staff', str(actor.pk), 'QA', 0))
    card = listing('color=blue&size=L&sale=1&min_price=90&in_stock=1&sort=price_asc')['products'][0]
    assert card['default_color'] == 'blue' and card['default_size'] == 'L' and card['price'] == 99
    assert next(row for row in card['variants'] if row['sku'] == 'BLUE-L')['available']
    assert listing('color=blue&size=L&max_price=20&in_stock=1')['total'] == 0


def test_pdp_preview_home_recommendations_cart_agree_and_reads_do_not_expire(inventory, client):
    _, product, _ = inventory
    counts = (InventoryMovement.objects.count(), ReservationLine.objects.count())
    pdp = client.get(reverse('catalog:detail', kwargs={'slug': product.slug}))
    assert pdp.status_code == 200
    assert {row['size']: row['available'] for row in pdp.context['product']['variants']} == {
        'missing': False, 'zero': False, 'reserved': False, 'M': True}
    assert pdp.context['product']['default_size'] == 'M'
    home = client.get(reverse('shop:home'))
    assert home.context['catalog_products'][0]['variants'] == pdp.context['product']['variants']
    assert collection_suggestions()[0]['variants'] == pdp.context['product']['variants']
    for size in ('missing', 'zero', 'reserved', 'M'):
        preview = client.get(reverse('catalog:variant_preview', kwargs={'slug': product.slug}), {'color': 'black', 'size': size})
        assert preview.json()['mode'] == 'inventory_test'
        assert preview.json()['variant']['available'] == (size == 'M')
        assert 'demo_available' not in preview.json()['variant']
        assert client.post(reverse('cart:add'), {'sku': f'AV-{size}', 'quantity': 1}).status_code == (302 if size == 'M' else 400)
    cart = client.get(reverse('cart:detail')).context['cart']
    assert cart['lines'][0]['max_quantity'] == 3 and cart['can_checkout']
    assert (InventoryMovement.objects.count(), ReservationLine.objects.count()) == counts


def test_fresh_reads_reflect_reservation_release_without_cache(inventory):
    actor, product, variants = inventory
    assert not CatalogVariantSelection().select(product_slug=product.slug, color='black', size='reserved').purchase_allowed
    services.release(actor=actor, variant_id=variants[2].pk, reservation_id='availability-held', quantity=1,
        expected_reservation_revision=1, now=timezone.now(),
        context=OperationContext('release', 'staff', str(actor.pk), 'QA', 2))
    assert CatalogVariantSelection().select(product_slug=product.slug, color='black', size='reserved').purchase_allowed
    assert listing('size=reserved&in_stock=1')['total'] == 1


def test_inventory_preserves_product_category_variant_and_currency_visibility(inventory, client):
    _, product, variants = inventory
    ProductVariant.objects.filter(pk=variants[3].pk).update(currency='USD')
    assert listing('in_stock=1')['total'] == 0
    with pytest.raises(CatalogSelectionError, match='catalog.currency_mismatch'):
        CatalogVariantSelection().select(product_slug=product.slug, color='black', size='M')
    ProductVariant.objects.filter(pk=variants[3].pk).update(currency='EUR', is_active=False)
    assert listing('in_stock=1')['total'] == 0
    assert not CatalogVariantSelection().select(product_slug=product.slug, color='black', size='M').purchase_allowed
    product.category.is_visible = False
    product.category.save(update_fields=['is_visible'])
    assert listing()['total'] == 0
    assert client.get(reverse('catalog:detail', kwargs={'slug': product.slug})).status_code == 404
    assert client.get(reverse('catalog:variant_preview', kwargs={'slug': product.slug}), {'color': 'black', 'size': 'M'}).status_code == 404


@pytest.mark.parametrize('count', [1, 50])
def test_cart_availability_is_bounded_without_per_sku_queries(inventory, count, django_assert_num_queries):
    from web.cart.session_cart import quote

    _, product, _ = inventory
    ProductVariant.objects.bulk_create([ProductVariant(product=product, sku=f'CART-{index}', color_code='blue',
        color_name_key='blue', size=str(index), price=10, demo_quantity=99) for index in range(count)])
    request = RequestFactory().get('/cart/')
    request.user = AnonymousUser()
    request.session = {}
    with django_assert_num_queries(2):
        result = quote(request, values={f'CART-{index}': 1 for index in range(count)})
        assert len(result['lines']) == count and not result['can_checkout']
        assert all(line['max_quantity'] == 0 and not line['stock_configured'] for line in result['lines'])


def test_wishlist_uses_same_inventory_snapshot(inventory, django_assert_num_queries):
    from web.wishlist.selectors import wishlist_products

    _, product, _ = inventory
    request = RequestFactory().get('/wishlist/')
    request.user = AnonymousUser()
    request.session = {'wishlist_guest': [product.pk]}
    with django_assert_num_queries(4):
        row = wishlist_products(request)[0]
        assert row['stock_mode'] == 'inventory_test'
        assert {variant['size']: variant['available'] for variant in row['variants']} == {
            'missing': False, 'zero': False, 'reserved': False, 'M': True}


@pytest.mark.parametrize('count', [1, 12])
def test_inventory_listing_query_budget_and_bounded_related_loading(inventory, count, django_assert_num_queries):
    _, product, _ = inventory
    for index in range(11):
        row = Product.objects.create(slug=f'extra-{index}', model_name=f'Extra {index}', brand=product.brand, category=product.category)
        ProductVariant.objects.create(product=row, sku=f'EXTRA-{index}', color_code='black', color_name_key='black', size='M', price=10)
    with django_assert_num_queries(12) as captured:
        result = listing('q=AV-M' if count == 1 else '')
        assert len(result['products']) == count
    sql = ' '.join(row['sql'] for row in captured.captured_queries)
    assert 'inventory_inventorymovement' not in sql and 'inventory_reservationline' not in sql
    with django_assert_num_queries(4):
        cards = [product_presentation(row, code='qa') for row in storefront_products().order_by('pk')[:count]]
        assert len(cards) == count


def test_staff_quantities_show_inventory_source_and_missing_state(inventory, client):
    actor, _, _ = inventory
    client.force_login(actor)
    response = client.get(reverse('staff:products'))
    assert response.status_code == 200
    row = list(response.context['products'])[0]
    assert row.available_quantity == 3 and row.unconfigured_variant_count == 1
    assert response.context['stock_mode'] == 'inventory_test'
    from web.staff.operations.presentation import summary
    from web.staff.operations.selectors import records
    rows = list(records('stock'))
    missing = next(row for row in rows if row.sku == 'AV-missing')
    zero = next(row for row in rows if row.sku == 'AV-zero')
    assert summary('stock', missing)[3]['key'] is True
    assert summary('stock', missing)[3]['value'] == 'staff.availability.unconfigured'
    assert summary('stock', zero)[3]['value'] == 0


def test_stock_price_order_and_card_sku_use_matching_inventory_variant(inventory):
    actor, product, variants = inventory
    ProductVariant.objects.filter(pk=variants[3].pk).update(price=99)
    other = Product.objects.create(slug='other', model_name='Other', brand=product.brand, category=product.category)
    variant = ProductVariant.objects.create(product=other, sku='OTHER', color_code='black',
        color_name_key='black', size='M', price=50, demo_quantity=0)
    services.initialize(actor=actor, variant_id=variant.pk, quantity=1,
        context=OperationContext('init-other', 'staff', str(actor.pk), 'QA', 0))
    result = listing('in_stock=1&sort=price_asc')['products']
    assert [(row['slug'], row['price'], row['default_size']) for row in result] == [
        ('other', 50, 'M'), ('availability', 99, 'M')]
    assert [row['slug'] for row in listing('in_stock=1&sort=price_desc')['products']] == ['availability', 'other']


def test_expired_holds_stay_conservative_and_gets_are_read_only(inventory, client):
    actor, product, variants = inventory
    old = timezone.now() - timedelta(hours=1)
    services.reserve(actor=actor, variant_id=variants[3].pk, reservation_id='expired-availability', quantity=3,
        expires_at=old + timedelta(minutes=30), now=old,
        context=OperationContext('hold-expired', 'staff', str(actor.pk), 'Isolated expiry read QA', 1))
    before = (StockBalance.objects.get(variant=variants[3]).reserved, InventoryMovement.objects.count())
    with CaptureQueriesContext(connection) as captured:
        assert listing('size=M&in_stock=1')['total'] == 0
        pdp = client.get(reverse('catalog:detail', kwargs={'slug': product.slug}))
        assert not any(row['available'] for row in pdp.context['product']['variants'])
        preview = client.get(reverse('catalog:variant_preview', kwargs={'slug': product.slug}), {'color': 'black', 'size': 'M'})
        assert preview.json()['variant']['available'] is False
        assert client.get(reverse('shop:home')).status_code == 200
        assert client.get(reverse('cart:detail')).status_code == 200
    writes = [row['sql'] for row in captured.captured_queries if row['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))]
    assert not writes
    assert (StockBalance.objects.get(variant=variants[3]).reserved, InventoryMovement.objects.count()) == before
    assert ReservationLine.objects.get(pk='expired-availability').state == 'held'


@pytest.mark.parametrize('language', ['de', 'ru'])
def test_staff_previews_stock_and_seo_use_inventory_in_both_languages(inventory, client, language, settings):
    from django.utils.translation import override

    from web.localization import translate_text
    from web.seo.structured_data import product_schema
    from web.staff.seo_workspace.selectors import page_schema

    actor, product, variants = inventory
    settings.SEO_PUBLIC_ORIGIN = 'https://example.com'
    client.force_login(actor)
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = language
    with override(language):
        for route in ('staff:product_preview',):
            response = client.get(reverse(route, kwargs={'pk': product.pk}))
            assert response.status_code == 200
            assert {row['size']: row['available'] for row in response.context['product']['variants']}['reserved'] is False
        preview = client.get(reverse('staff:product_variant_preview', kwargs={'pk': product.pk}), {'color': 'black', 'size': 'missing'})
        assert preview.status_code == 200 and not preview.json()['variant']['available']
        assert 'private' in preview['Cache-Control']
        for route, kwargs in [('staff:products', {}), ('staff:stock', {}), ('staff:stock_detail', {'pk': variants[0].pk})]:
            response = client.get(reverse(route, kwargs=kwargs))
            assert response.status_code == 200
            assert response.wsgi_request.LANGUAGE_CODE == language
            keys = ('staff.availability.unconfigured', 'staff.availability.quantity', 'staff.availability.inventory_notice') \
                if route == 'staff:products' else ('staff.inventory.missing', 'staff.inventory.source')
            if route == 'staff:stock':
                keys += ('staff.inventory.on_hand',)
            assert all(translate_text(key) in response.content.decode() for key in keys)
        schema = product_schema({'product': product_presentation(storefront_products().get(pk=product.pk), code='qa')}, 'https://example.test/product/')
        assert 'offers' not in json.loads(schema)['@graph'][0]
        generated = page_schema({'kind': 'product', 'key': product.slug, 'published': {}, 'path': '/product/'}, language)
        assert generated and 'offers' not in json.loads(generated)['@graph'][0]
