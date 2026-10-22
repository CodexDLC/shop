import json
from pathlib import Path

import pytest
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django.utils.translation import override

from web.catalog.models import Product
from web.staff.models import CabinetPreferences

pytestmark = pytest.mark.django_db

@pytest.fixture(autouse=True)
def language_scope():
    with override('de'):
        yield



@pytest.fixture
def owner(client, django_user_model):
    account = django_user_model.objects.create_superuser(username='workspace-owner', email='owner@example.test', password='test-only')
    client.force_login(account)
    return client


def test_top_groups_and_right_language_are_separate_from_left_settings(owner):
    response = owner.get('/ru/staff/')
    html = response.content.decode()
    assert response.status_code == 200
    assert [group['key'] for group in response.context['staff_primary_groups']] == ['shop', 'operations', 'management']
    assert 'Магазин' in html and 'Операции' in html and 'Управление' in html
    header = html.split('<header class="cab-topbar">')[1].split('</header>')[0]
    assert 'data-staff-language' in header
    footer = html.split('data-staff-settings')[1].split('</div>')[0]
    assert 'data-staff-language' not in footer
    assert CabinetPreferences.objects.count() == 0


@pytest.mark.parametrize('name,module', [('products','catalog'),('orders','operations'),('payments','management')])
def test_group_changes_left_navigation(owner,name,module):
    response=owner.get(reverse(f'staff:{name}'))
    assert response.status_code == 200
    assert response.context['staff_workspace_group'] == module
    rows=response.context['staff_sidebar_rows']
    assert any(row['active'] and str(row['item'].url)==reverse(f'staff:{name}') for row in rows)


def test_dashboard_counts_and_product_state_filter_use_real_records(owner):
    call_command('seed_demo_catalog')
    product=Product.objects.first()
    product.is_active=False
    product.editorial_state='review'
    product.save(update_fields=['is_active','editorial_state'])
    response=owner.get(reverse('staff:home'))
    cards={card['label']:card['count'] for card in response.context['workspace_cards']}
    assert cards['staff.workspace.overview.products'] == Product.objects.count()
    assert cards['staff.workspace.overview.review'] == 1
    response=owner.get(reverse('staff:products'),{'state':'review'})
    assert list(response.context['products']) == [product]


def test_limited_staff_sees_only_permitted_destinations_and_counts(client,django_user_model):
    account=django_user_model.objects.create_user(username='stock-only',is_staff=True)
    account.user_permissions.add(Permission.objects.get(content_type__app_label='catalog',codename='view_productvariant'))
    client.force_login(account)
    response=client.get(reverse('staff:home'))
    assert response.status_code == 200
    assert response.context['workspace_cards'] == []
    assert [group['key'] for group in response.context['staff_primary_groups']] == ['operations']
    assert response.context['staff_primary_groups'][0]['url'] == reverse('staff:stock')
    assert client.get(reverse('staff:workspace_preview',kwargs={'section':'integrations'})).status_code == 403


@pytest.mark.parametrize('section', ['shipping','returns','analytics','content','integrations','operations_settings'])
def test_future_design_pages_are_honest_get_only(owner,section):
    url=reverse('staff:workspace_preview',kwargs={'section':section})
    response=owner.get(url)
    assert response.status_code == 200
    html=response.content.decode()
    assert 'fieldset disabled' in html
    assert 'Nicht angebunden' in html
    assert owner.post(url,{}).status_code == 405
    assert 'noindex' in response['X-Robots-Tag']


def test_new_routes_require_staff_even_for_customer_with_permission(client,django_user_model):
    account=django_user_model.objects.create_user(username='not-staff')
    account.user_permissions.add(*Permission.objects.all())
    client.force_login(account)
    for url in ['/ru/staff/orders/','/ru/staff/catalog/brands/','/ru/staff/workspace/shipping/']:
        assert client.get(url).status_code == 403


def test_language_change_from_workspace_uses_csrf_and_preserves_destination(django_user_model):
    client=Client(enforce_csrf_checks=True)
    client.force_login(django_user_model.objects.create_superuser(username='language-owner',email='language@example.test',password='test-only'))
    response=client.get('/ru/staff/orders/?q=test')
    assert response.status_code == 200
    assert client.post('/ru/i18n/setlang/',{'language':'de','next':'/ru/staff/orders/?q=test'}).status_code==403
    response=client.post('/ru/i18n/setlang/',{'language':'de','next':'/ru/staff/orders/?q=test','csrfmiddlewaretoken':client.cookies['csrftoken'].value})
    assert response.url=='/staff/orders/?q=test'


def test_all_workspace_navigation_labels_are_in_both_catalogs():
    root=Path('src/web/localization/messages')
    de=json.loads((root/'de.json').read_text(encoding='utf-8'))
    ru=json.loads((root/'ru.json').read_text(encoding='utf-8'))
    for key in de:
        if key.startswith('staff.workspace.'):
            assert ru.get(key),key
    with override('ru'):
        assert reverse('staff:orders').startswith('/ru/staff/')
