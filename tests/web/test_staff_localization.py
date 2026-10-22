import json
from pathlib import Path
from string import Formatter

import pytest
from django.test import Client
from django.urls import reverse
from django.utils.translation import override

from web.localization import translate_text


@pytest.mark.django_db
def test_russian_staff_routes_login_and_language_switch(django_user_model):
    client = Client(enforce_csrf_checks=True)
    user = django_user_model.objects.create_superuser(username="ru-editor", email="editor@example.test", password="test-only")
    client.force_login(user)
    page = client.get("/ru/staff/catalog/?q=Model")
    assert page.status_code == 200
    html = page.content.decode()
    assert 'lang="ru"' in html
    assert '/ru/staff/catalog/new/' in html
    assert 'name="language"' in html
    assert 'Русский' in html
    token = client.cookies['csrftoken'].value
    assert client.post('/ru/i18n/setlang/', {'language': 'de', 'next': '/ru/staff/catalog/?q=Model'}).status_code == 403
    changed = client.post('/ru/i18n/setlang/', {'language': 'de', 'next': '/ru/staff/catalog/?q=Model', 'csrfmiddlewaretoken': token})
    assert changed.status_code == 302
    assert changed.url == '/staff/catalog/?q=Model'
    german = client.get(changed.url)
    assert german.status_code == 200 and 'lang="de"' in german.content.decode()
    assert client.post('/i18n/setlang/', {'language': 'ru', 'next': '/staff/catalog/?q=Model', 'csrfmiddlewaretoken': token}).url == '/ru/staff/catalog/?q=Model'
    anonymous = Client().get('/ru/staff/catalog/')
    assert anonymous.status_code == 302 and '/ru/accounts/login/' in anonymous.url


def test_all_staff_keys_have_russian_translations_and_matching_placeholders():
    root = Path('src/web/localization/messages')
    de = json.loads((root / 'de.json').read_text(encoding='utf-8'))
    ru = json.loads((root / 'ru.json').read_text(encoding='utf-8'))
    def parameters(value):
        return {field for _, field, _, _ in Formatter().parse(value) if field is not None}
    for key, value in de.items():
        if key.startswith('staff.'):
            assert key in ru and ru[key].strip(), key
            assert parameters(value) == parameters(ru[key]), key
            with override('ru'):
                assert translate_text(key) == ru[key], key
    with override('ru'):
        assert reverse('staff:products') == '/ru/staff/catalog/'


@pytest.mark.django_db
def test_russian_product_tabs_and_fingerprint_are_language_independent(client, django_user_model):
    from django.core.management import call_command

    from web.catalog.models import Product
    from web.staff.product_editing import content_fingerprint

    call_command('seed_demo_catalog')
    product = Product.objects.first()
    user = django_user_model.objects.create_superuser(username='ru-owner', email='owner@example.test', password='test-only')
    client.force_login(user)
    with override('de'):
        fingerprint = content_fingerprint(product)
    with override('ru'):
        assert content_fingerprint(product) == fingerprint
    for suffix, key in (('', 'staff.product_tabs.main'), ('variants/', 'staff.product_tabs.variants'),
                        ('information/', 'staff.product_tabs.information'), ('photos/', 'staff.product_tabs.photos'),
                        ('publication/', 'staff.product_tabs.publication')):
        response = client.get(f'/ru/staff/catalog/{product.pk}/{suffix}')
        assert response.status_code == 200
        with override('ru'):
            assert translate_text(key) in response.content.decode()
        assert '/ru/staff/catalog/' in response.content.decode()
        assert response['X-Robots-Tag'].startswith('noindex')


@pytest.mark.django_db
def test_russian_editor_stale_error_is_translated(client, django_user_model):
    from django.core.management import call_command

    from web.catalog.models import Product

    call_command('seed_demo_catalog')
    product = Product.objects.first()
    product.is_active = False
    product.save(update_fields=['is_active'])
    user = django_user_model.objects.create_superuser(username='ru-errors', email='errors@example.test', password='test-only')
    client.force_login(user)
    response = client.post(f'/ru/staff/catalog/{product.pk}/information/', {'original_state': 'invalid'})
    assert response.status_code == 409
    with override('ru'):
        assert translate_text('staff.product_form.stale') in response.content.decode()
    with override('de'):
        assert translate_text('staff.product_form.stale') not in response.content.decode()
