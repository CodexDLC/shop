import pytest
from django.core.management import call_command
from django.urls import reverse

from web.catalog.models import Product, ProductImage

pytestmark = pytest.mark.django_db


def test_pdp_renders_real_gallery_and_accessible_zoom(client, django_assert_num_queries):
    call_command('seed_demo_catalog')
    product = Product.objects.get(slug='manstore-m2223')
    ProductImage.objects.filter(product=product).delete()
    urls = ['https://example.test/front.jpg', 'https://example.test/back.jpg']
    for index, url in enumerate(urls):
        ProductImage.objects.create(product=product, image_url=url, position=index, alt_key='catalog.photo.demo')
    with django_assert_num_queries(9):
        response = client.get(reverse('catalog:detail', kwargs={'slug': product.slug}))
    assert response.context['product']['initial_gallery'] == urls
    html = response.content.decode()
    assert html.count('<a data-gallery-thumbnail ') == 2
    assert 'data-product-gallery' in html
    assert 'data-gallery-main' in html
    assert '<dialog' in html and 'data-gallery-dialog' in html
    assert 'data-gallery-close' in html
    assert 'product-gallery.js' in html
    assert '[catalog.gallery.' not in html


def test_pdp_without_photos_has_honest_empty_gallery(client):
    call_command('seed_demo_catalog')
    product = Product.objects.get(slug='manstore-m2223')
    ProductImage.objects.filter(product=product).delete()
    response = client.get(reverse('catalog:detail', kwargs={'slug': product.slug}))
    assert response.context['product']['initial_gallery'] == []
    assert 'data-gallery-empty' in response.content.decode()
    assert 'src=""' not in response.content.decode()
