from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from web.catalog.models import Product, ProductVariant
from web.wishlist.selectors import wishlist_products
from web.wishlist.session import MAX_PRODUCTS, product_ids

pytestmark = pytest.mark.django_db


@pytest.fixture
def product():
    call_command('seed_demo_catalog')
    return Product.objects.first()


def test_wishlist_mutations_require_csrf_and_post(product):
    client = Client(enforce_csrf_checks=True)
    assert client.get(reverse('wishlist:add')).status_code == 405
    assert client.post(reverse('wishlist:add'), {'product_id': product.pk}).status_code == 403
    assert Client().post(reverse('wishlist:add'), {'product_id': 'invalid'}).status_code == 400


def test_guest_save_deduplicate_remove_and_render_without_get_mutation(product):
    client = Client()
    for _ in range(2):
        response = client.post(reverse('wishlist:add'), {'product_id': product.pk},
                               HTTP_ACCEPT='application/json')
        assert response.json() == {'count': 1, 'saved': True}
    before = dict(client.session)
    page = client.get(reverse('wishlist:detail'))
    assert 'no-store' in page['Cache-Control']
    html = page.content.decode()
    assert product.model_name in html
    assert dict(client.session) == before
    assert product.model_name not in Client().get(reverse('wishlist:detail')).content.decode()
    response = client.post(reverse('wishlist:remove'), {'product_id': product.pk},
                           HTTP_ACCEPT='application/json')
    assert response.json() == {'count': 0, 'saved': False}


def test_principal_binding_and_active_variants(product):
    client = Client()
    client.post(reverse('wishlist:add'), {'product_id': product.pk})
    user = get_user_model().objects.create_user(username='wishlist-owner')
    client.force_login(user)
    assert client.get(reverse('wishlist:detail')).context['wishlist_products'] == []
    client.post(reverse('wishlist:add'), {'product_id': product.pk})
    ProductVariant.objects.filter(product=product).update(is_active=False)
    assert client.get(reverse('wishlist:detail')).context['wishlist_products'] == []
    assert client.post(reverse('wishlist:add'), {'product_id': product.pk}).status_code == 400


def test_wishlist_does_not_label_foreign_currency_as_euros(product):
    client = Client()
    client.post(reverse('wishlist:add'), {'product_id': product.pk})
    ProductVariant.objects.filter(product=product).update(currency='USD')
    assert client.get(reverse('wishlist:detail')).context['wishlist_products'] == []
    assert client.post(reverse('wishlist:add'), {'product_id': product.pk}).status_code == 400


def test_bounded_ids_and_queries_do_not_grow_per_product(product, django_assert_num_queries):
    products = [product]
    for number in range(MAX_PRODUCTS):
        item = Product.objects.create(slug=f'wishlist-{number}', brand=product.brand,
                                      category=product.category, model_name=f'Saved {number}')
        ProductVariant.objects.create(product=item, sku=f'WISH-{number}', color_code='black',
                                      color_name_key='catalog.color.black', size='M', price='10.00')
        products.append(item)
    client = Client()
    session = client.session
    session['wishlist_guest'] = [item.pk for item in products[:MAX_PRODUCTS]]
    session.save()
    assert client.post(reverse('wishlist:add'), {'product_id': products[-1].pk}).status_code == 400
    request = SimpleNamespace(session={'wishlist_guest': [item.pk for item in products[:12]]},
                              user=SimpleNamespace(is_authenticated=False))
    with django_assert_num_queries(4):
        assert len(wishlist_products(request)) == 12
    request.session['wishlist_guest'] = ['bad', -1, True, product.pk, product.pk]
    assert product_ids(request) == [product.pk]
