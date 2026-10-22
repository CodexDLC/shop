from html.parser import HTMLParser
from pathlib import Path

import pytest
from django.core.management import call_command
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_legacy_preview_cannot_hide_the_native_size_dialog():
    source = (Path(__file__).resolve().parents[2] / 'src/web/static/storefront/reference-navigation.js').read_text()
    assert "document.getElementById('sizeGuideModal')?.classList.add('hidden')" not in source


class ContentText(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.skip = False
        self.parts = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip = True

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = False

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def test_pdp_replaces_invented_characteristics_sizes_and_ratings(client):
    call_command('seed_demo_catalog')
    response = client.get(reverse('catalog:detail', kwargs={'slug': 'manstore-m2223'}))
    html = response.content.decode()
    text = ' '.join(ContentText(html).parts)
    assert '4.9' not in text
    assert '(48)' not in text
    assert '88% Polyamid' not in text
    assert '78 – 83' not in text
    assert 'OEKO-TEX' not in text
    # The seed has an explicit legacy demo description, which remains a valid fallback.
    assert 'data-information-empty' not in html
    assert 'Demonstrationsdaten:' in text
    assert 'data-size-guide-empty' in html
    assert 'data-reviews-empty' in html
    assert '<dialog' in html and 'id="sizeGuideModal"' in html
    assert 'data-product-tabs' in html
    assert 'product-information.js' in html
    assert '[catalog.information.' not in html


def test_pdp_uses_escaped_editorial_data_and_only_approved_reviews(client, django_assert_num_queries):
    from web.catalog.models import Product, ProductInformation, ProductReview, SizeGuide, SizeGuideRow

    call_command('seed_demo_catalog')
    product = Product.objects.get(slug='manstore-m2223')
    ProductInformation.objects.create(product=product, description='<script>editorial()</script>',
                                     composition='Test composition', care='Test care', fit='Test fit',
                                     origin='Test origin', certification='Test certificate')
    guide = SizeGuide.objects.create(brand=product.brand, title='Test manufacturer chart',
                                    source_label='Isolated test fixture', is_published=True)
    SizeGuideRow.objects.create(guide=guide, size='M', waist_min_cm=80, waist_max_cm=90)
    ProductReview.objects.create(product=product, rating=2, status='approved',
                                 author_display='<img onerror="bad()">', body='<script>review()</script>')
    ProductReview.objects.create(product=product, rating=5, status='pending', body='DO-NOT-PUBLISH')
    # Includes one request-memoized public seller identity read for the shared footer.
    # Two bounded SEO reads: the published page override and its automatic rule.
    with django_assert_num_queries(13):
        response = client.get(reverse('catalog:detail', kwargs={'slug': product.slug}))
    html = response.content.decode()
    assert response.context['review_summary']['count'] == 1
    assert response.context['review_summary']['average'] == 2
    assert 'Test composition' in html and 'Test manufacturer chart' in html
    assert 'data-measurement-cm="80–90"' in html
    assert 'data-measurement-inch="31.5–35.4"' in html
    assert '&lt;script&gt;editorial()&lt;/script&gt;' in html
    assert '&lt;script&gt;review()&lt;/script&gt;' in html
    assert '<script>review()' not in html and '<script>editorial()' not in html
    assert 'DO-NOT-PUBLISH' not in html


def test_other_language_shows_german_fallback_label(client):
    from web.catalog.models import Product, ProductInformation

    call_command('seed_demo_catalog')
    product = Product.objects.get(slug='manstore-m2223')
    ProductInformation.objects.create(product=product, description='German test content')
    response = client.get('/ru/produkt/manstore-m2223/')
    assert response.status_code == 200
    assert 'German test content' in response.content.decode()
    assert 'Produktangaben in: DE' in response.content.decode()
