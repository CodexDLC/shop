from html.parser import HTMLParser

import pytest
from django.test import Client
from django.urls import reverse
from django.utils.translation import override


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def by_id(self, identifier):
        return next(attrs for _, attrs in self.elements if attrs.get('id') == identifier)


@pytest.mark.django_db
@pytest.mark.parametrize('route,form_id', [
    ('support:help', 'serviceContactForm'), ('support:help_mobile', 'contactForm'),
])
def test_help_exposes_local_contact_form_without_fake_delivery(route, form_id):
    response = Client().get(reverse(route))
    assert response.status_code == 200
    html = response.content.decode()
    elements = Elements(html)
    assert elements.by_id(form_id)['action'] == reverse('support:contact')
    assert elements.by_id(form_id)['method'] == 'post'
    assert elements.by_id(form_id)['data-real-support'] == 'true'
    assert 'handleFormSubmit' not in html
    assert 'id="contact-success"' not in html
    assert 'id="contactSuccess"' not in html
    for tag, attrs in elements.elements:
        if attrs.get('data-contact-draft') == 'true':
            assert 'href' not in attrs
        if tag == 'a':
            assert not attrs.get('href', '').startswith(('tel:', 'mailto:', 'https://wa.me/'))
    # Actual submitted fields are allowlisted and work without JavaScript.
    form_html = html.split(f'id="{form_id}"', 1)[1].split('</form>', 1)[0]
    fields = {attrs.get('name') for tag, attrs in Elements(form_html).elements
              if tag in {'input', 'select', 'textarea'}}
    assert {'csrfmiddlewaretoken', 'name', 'email', 'topic', 'message', 'website'} <= fields


@pytest.mark.django_db
@pytest.mark.parametrize('route', ['support:help', 'support:help_mobile'])
def test_faq_exposes_recovery_and_accessible_button_controls(route):
    html = Client().get(reverse(route)).content.decode()
    elements = Elements(html)
    assert elements.by_id('faq-no-results')['role'] == 'status'
    assert elements.by_id('faq-reset')['type'] == 'button'
    triggers = [attrs for tag, attrs in elements.elements if tag == 'button' and (
        'data-faq-trigger' in attrs or 'faq-trigger' in attrs.get('class', '').split()
    )]
    assert triggers
    assert all(attrs['type'] == 'button' and attrs['aria-expanded'] == 'false' for attrs in triggers)
    assert 'Keine passenden Hilfethemen gefunden.' in html
    assert 'ArrowDown' in html


@pytest.mark.django_db
def test_404_search_submits_query_to_localized_catalog_without_javascript():
    with override('ru'):
        html = Client().get(reverse('support:not_found')).content.decode()
        elements = Elements(html)
        forms = [attrs for tag, attrs in elements.elements if tag == 'form']
        assert any(attrs.get('action') == reverse('catalog:search')
                   and attrs.get('method') == 'get'
                   and attrs.get('data-real-catalog') == 'true' for attrs in forms)
        assert elements.by_id('luxury-search-input')['name'] == 'q'
        assert '#search=' not in html
        response = Client().get(reverse('catalog:search'), {'q': 'no-such-test-product'})
        assert response.status_code == 200
        assert response.context['catalog_listing']['query'] == 'no-such-test-product'
        assert response.context['catalog_listing']['total'] == 0
