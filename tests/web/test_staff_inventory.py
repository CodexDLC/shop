from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import OperationalError, connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import override

from codex_ecommerce.inventory import OperationContext
from web.catalog.models import Brand, Category, Product, ProductVariant
from web.inventory import services
from web.inventory.models import InventoryMovement, StockBalance

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def owner():
    return get_user_model().objects.create_user(username='inventory-owner', is_staff=True, is_superuser=True)


@pytest.fixture
def variant():
    brand = Brand.objects.create(slug='warehouse-brand', name='Warehouse brand')
    category = Category.objects.create(slug='warehouse-category', name_key='warehouse.category')
    product = Product.objects.create(slug='warehouse-product', model_name='Warehouse product', brand=brand, category=category)
    return ProductVariant.objects.create(product=product, sku='WAREHOUSE-M', color_code='black',
        color_name_key='color.black', size='M', price='20.00', demo_quantity=99)


def staff(*permissions):
    user = get_user_model().objects.create_user(username='warehouse-reader', is_staff=True)
    user.user_permissions.add(*Permission.objects.filter(content_type__app_label='inventory', codename__in=permissions))
    return user


def detail(variant):
    return reverse('staff:stock_detail', kwargs={'pk': variant.pk})


def command(variant, action):
    return reverse('staff:stock_command', kwargs={'pk': variant.pk, 'action': action})


def payload(client, variant, action, quantity=5):
    response = client.get(detail(variant))
    form = response.context['inventory_forms'][action]
    return {form.add_prefix('intent'): form.initial['intent'], form.add_prefix('quantity'): quantity,
        form.add_prefix('reason'): 'Verified count'}


def initialize(owner, variant, quantity=10):
    return services.initialize(actor=owner, variant_id=variant.pk, quantity=quantity,
        context=OperationContext('fixture', 'staff', str(owner.pk), 'Verified count', 0))


def test_old_catalog_permission_cannot_bypass_inventory(client, variant):
    user = staff()
    user.user_permissions.add(Permission.objects.get(content_type__app_label='catalog', codename='view_productvariant'))
    client.force_login(user)
    assert client.get(reverse('staff:stock')).status_code == 403
    assert client.get(detail(variant)).status_code == 403
    assert client.post(command(variant, 'initialize'), {}).status_code == 403


@pytest.mark.parametrize('section,permission', [('balance', 'view_stockbalance'),
    ('history', 'view_inventorymovement'), ('reservations', 'view_reservationline')])
def test_independent_read_permissions_and_navigation(client, variant, section, permission):
    client.force_login(staff(permission))
    response = client.get(reverse('staff:stock'))
    assert response.status_code == 200
    assert reverse('staff:stock') in response.content.decode()
    assert [str(entry.url) for entry in response.context['cabinet_topbar_entries']
        if str(entry.url) == reverse('staff:orders')] == []
    assert any(str(entry.url) == reverse('staff:stock') for entry in response.context['cabinet_topbar_entries'])
    assert not response.context['cabinet_settings_url']
    assert not response.context['staff_global_settings_url']
    assert not response.context['cabinet_quick_access']
    assert client.get(detail(variant), {'section': section}).status_code == 200
    for other in {'balance', 'history', 'reservations'} - {section}:
        assert client.get(detail(variant), {'section': other}).status_code == 403
    assert client.get(reverse('staff:orders')).status_code == 403
    assert client.get(reverse('staff:customers')).status_code == 403
    assert client.get(reverse('staff:products')).status_code == 403


@pytest.mark.parametrize('flag', ['is_staff', 'is_active'])
def test_inactive_and_nonstaff_direct_endpoints(client, owner, variant, flag):
    client.force_login(owner)
    data = payload(client, variant, 'initialize')
    setattr(owner, flag, False)
    owner.save()
    assert client.get(detail(variant)).status_code in {302, 403}
    assert client.post(command(variant, 'initialize'), data).status_code in {302, 403}
    assert not StockBalance.objects.exists()


def test_missing_zero_filters_explicit_low_threshold_and_pagination(client, owner, variant):
    client.force_login(owner)
    response = client.get(reverse('staff:stock'))
    assert response.context['page_obj'].object_list[0].stock_on_hand is None
    assert '>99</td>' not in response.content.decode()
    initialize(owner, variant, 0)
    assert client.get(reverse('staff:stock'), {'status': 'missing'}).context['page_obj'].paginator.count == 0
    assert client.get(reverse('staff:stock'), {'status': 'unavailable'}).context['page_obj'].paginator.count == 1
    assert client.get(reverse('staff:stock'), {'status': 'low', 'threshold': '0'}).context['page_obj'].paginator.count == 1
    assert client.get(reverse('staff:stock'), {'status': 'low', 'threshold': '-1'}).context['filter_form'].errors
    ProductVariant.objects.bulk_create([ProductVariant(product=variant.product, sku=f'WAREHOUSE-{i}', color_code='black',
        color_name_key='black', size=f'S{i}', price='10') for i in range(27)])
    response = client.get(reverse('staff:stock'), {'q': 'WAREHOUSE', 'page': '2'})
    assert len(response.context['page_obj'].object_list) == 3
    assert 'q=WAREHOUSE' in response.content.decode()


def test_initialize_receive_adjust_prg_replay_and_service_only(client, owner, variant):
    from web.localization import translate_text

    client.force_login(owner)
    for action, quantity, expected in [('initialize', 0, 0), ('receive', 7, 7), ('adjust', 4, 4)]:
        data = payload(client, variant, action, quantity)
        with patch(f'web.staff.inventory_workspace.command_view.services.{action}', wraps=getattr(services, action)) as service:
            assert client.post(command(variant, action), data).status_code == 302
            assert service.call_count == 1
        response = client.post(command(variant, action), data, follow=True)
        stock = StockBalance.objects.get()
        assert translate_text('staff.inventory.saved', on_hand=expected, reserved=0,
            available=expected, revision=stock.revision) in response.content.decode()
        assert StockBalance.objects.get().on_hand == expected
    assert InventoryMovement.objects.count() == 3
    variant.refresh_from_db()
    assert variant.demo_quantity == 99


def test_signed_actor_target_action_and_payload_replay_conflicts(client, owner, variant):
    client.force_login(owner)
    data = payload(client, variant, 'initialize')
    forged = dict(data, **{'initialize-intent': data['initialize-intent'] + 'x'})
    assert client.post(command(variant, 'initialize'), forged).status_code == 400
    assert client.post(command(variant, 'receive'), data).status_code == 400
    second = ProductVariant.objects.create(product=variant.product, sku='OTHER', color_code='red',
        color_name_key='red', size='M', price='1')
    assert client.post(command(second, 'initialize'), data).status_code == 400
    another = get_user_model().objects.create_user(username='another-owner', is_staff=True, is_superuser=True)
    client.force_login(another)
    assert client.post(command(variant, 'initialize'), data).status_code == 400
    client.force_login(owner)
    assert client.post(command(variant, 'initialize'), data).status_code == 302
    response = client.post(command(variant, 'initialize'), dict(data, **{'initialize-quantity': 6}))
    assert response.status_code == 409
    assert InventoryMovement.objects.count() == 1


def test_stale_preserves_input_and_reason(client, owner, variant):
    client.force_login(owner)
    initialize(owner, variant)
    data = payload(client, variant, 'adjust', 6)
    services.receive(actor=owner, variant_id=variant.pk, quantity=1,
        context=OperationContext('concurrent', 'staff', str(owner.pk), 'Delivery', 1))
    response = client.post(command(variant, 'adjust'), data)
    assert response.status_code == 409
    assert response.context['inventory_forms']['adjust'].data['adjust-quantity'] == '6'
    assert response.context['inventory_forms']['adjust'].data['adjust-intent'] == data['adjust-intent']
    assert 'Verified count' in response.content.decode()
    assert StockBalance.objects.get().on_hand == 11


@pytest.mark.parametrize('quantity,reason', [(-1, 'Valid'), (1, ''), (9223372036854775808, 'Valid')])
def test_invalid_input_cannot_write(client, owner, variant, quantity, reason):
    client.force_login(owner)
    data = dict(payload(client, variant, 'initialize', quantity), **{'initialize-reason': reason})
    assert client.post(command(variant, 'initialize'), data).status_code == 400
    assert not InventoryMovement.objects.exists()


def test_readonly_cannot_post_and_revoked_replay_cannot_post(client, owner, variant):
    client.force_login(owner)
    data = payload(client, variant, 'initialize')
    assert client.post(command(variant, 'initialize'), data).status_code == 302
    owner.is_superuser = False
    owner.save()
    owner.user_permissions.add(Permission.objects.get(content_type__app_label='inventory', codename='view_stockbalance'))
    assert client.post(command(variant, 'initialize'), data).status_code == 403
    assert not client.get(detail(variant)).context['inventory_forms']


def test_csrf_and_get_never_mutate(client, owner, variant):
    csrf = Client(enforce_csrf_checks=True)
    csrf.force_login(owner)
    data = payload(csrf, variant, 'initialize')
    assert csrf.post(command(variant, 'initialize'), data).status_code == 403
    assert csrf.get(command(variant, 'initialize')).status_code == 405
    assert not StockBalance.objects.exists()


def test_below_reserved_reconciliation_history_and_expiry(client, owner, variant):
    from web.localization import translate_text

    client.force_login(owner)
    initialize(owner, variant)
    now = timezone.now()
    services.reserve(actor=owner, variant_id=variant.pk, reservation_id='staff-ui-hold', quantity=7,
        expires_at=now + timedelta(minutes=1), now=now,
        context=OperationContext('hold', 'staff', str(owner.pk), 'Reservation', 1))
    response = client.post(command(variant, 'adjust'), payload(client, variant, 'adjust', 6))
    assert response.status_code == 409
    response = client.get(detail(variant))
    assert response.context['reconciliation']['matches']
    assert response.context['reconciliation']['line_reserved'] == 7
    history = client.get(detail(variant), {'section': 'history'})
    assert history.context['history_page'].paginator.count == 2
    assert 'before_reservation' not in history.content.decode()
    with patch('web.staff.inventory_workspace.detail_view.timezone.now', return_value=now + timedelta(minutes=2)):
        response = client.get(detail(variant), {'section': 'reservations'})
    assert response.context['expired_count'] == 1
    data = {'expire-intent': response.context['cleanup_form'].initial['intent']}
    with patch('web.staff.inventory_workspace.command_view.timezone.now', return_value=now + timedelta(minutes=2)):
        response = client.post(command(variant, 'expire'), data, follow=True)
        assert translate_text('staff.inventory.cleanup_result', scanned=1, expired=1, skipped=0,
            more=translate_text('staff.inventory.no')) in response.content.decode()
        assert client.post(command(variant, 'expire'), data).status_code == 302
    assert StockBalance.objects.get().reserved == 0
    assert InventoryMovement.objects.filter(kind='expire').count() == 1


@pytest.mark.parametrize('language', ['ru', 'de'])
def test_below_reserved_error_explains_counts_preserves_input_and_keeps_cas(client, owner, variant, language):
    from web.localization import translate_text

    initialize(owner, variant)
    client.force_login(owner)
    with override(language):
        old_data = payload(client, variant, 'adjust', 6)
        now = timezone.now()
        services.reserve(actor=owner, variant_id=variant.pk, reservation_id='below-floor-hold', quantity=7,
            expires_at=now + timedelta(minutes=10), now=now,
            context=OperationContext('floor-hold', 'staff', str(owner.pk), 'Reservation', 1))
        response = client.post(command(variant, 'adjust'), old_data)
        assert response.status_code == 409
        assert translate_text('staff.inventory.error.stale_revision') in response.content.decode()
        data = payload(client, variant, 'adjust', 6)
        with patch('web.staff.inventory_workspace.command_view.services.adjust', wraps=services.adjust) as service:
            response = client.post(command(variant, 'adjust'), data)
        assert service.call_count == 1
        assert response.status_code == 409
        assert translate_text('staff.inventory.error.below_reserved', quantity=6, reserved=7) in response.content.decode()
        assert response.context['inventory_forms']['adjust'].data.dict() == {key: str(value) for key, value in data.items()}
        assert detail(variant) + '?section=reservations' in response.content.decode()
        assert StockBalance.objects.get().on_hand == 10
        assert StockBalance.objects.get().reserved == 7
        assert InventoryMovement.objects.count() == 2


def test_late_service_failure_rolls_back_http_command(client, owner, variant):
    client.force_login(owner)
    data = payload(client, variant, 'initialize')
    with patch('web.inventory.services.StaffAuditEvent.objects.create', side_effect=RuntimeError('failure')):
        with pytest.raises(RuntimeError, match='failure'):
            client.post(command(variant, 'initialize'), data)
    assert not StockBalance.objects.exists()
    assert not InventoryMovement.objects.exists()
    assert client.post(command(variant, 'initialize'), data).status_code == 302


def test_read_selectors_constant_query_budgets(owner, variant):
    from web.staff.inventory_workspace.selectors import variants

    initialize(owner, variant)
    for count in (1, 8):
        for index in range(count):
            services.receive(actor=owner, variant_id=variant.pk, quantity=1,
                context=OperationContext(f'budget-{count}-{index}', 'staff', str(owner.pk), 'Delivery',
                    StockBalance.objects.get().revision))
        with CaptureQueriesContext(connection) as queries:
            rows = list(variants())
            assert rows[0].product.model_name
        assert len(queries) == 1


@pytest.mark.parametrize('action', ['initialize', 'receive', 'adjust', 'expire'])
def test_every_command_needs_independent_action_permission(client, variant, action):
    user = staff('view_stockbalance', 'view_inventorymovement', 'view_reservationline')
    client.force_login(user)
    assert client.post(command(variant, action), {}).status_code == 403


@pytest.mark.parametrize('permission', ['view_stockbalance', 'view_inventorymovement', 'view_reservationline'])
def test_operations_settings_stock_link_uses_inventory_read_permissions(client, permission):
    user = staff()
    user.user_permissions.add(Permission.objects.get(content_type__app_label='orders', codename='view_order'),
        Permission.objects.get(content_type__app_label='catalog', codename='view_productvariant'))
    client.force_login(user)
    url = reverse('staff:workspace_preview', kwargs={'section': 'operations_settings'})
    response = client.get(url)
    assert reverse('staff:stock') not in [link['url'] for card in response.context['settings_cards'] for link in card['links']]
    user.user_permissions.add(Permission.objects.get(content_type__app_label='inventory', codename=permission))
    response = client.get(url)
    assert reverse('staff:stock') in [link['url'] for card in response.context['settings_cards'] for link in card['links']]


def test_missing_and_zero_have_distinct_actions_and_stale_replay_returns_original(client, owner, variant):
    client.force_login(owner)
    response = client.get(detail(variant))
    assert list(response.context['inventory_forms']) == ['initialize']
    data = payload(client, variant, 'initialize', 0)
    assert client.post(command(variant, 'initialize'), data).status_code == 302
    assert set(client.get(detail(variant)).context['inventory_forms']) == {'receive', 'adjust'}
    services.receive(actor=owner, variant_id=variant.pk, quantity=3,
        context=OperationContext('after-original', 'staff', str(owner.pk), 'Delivery', 1))
    response = client.post(command(variant, 'initialize'), data, follow=True)
    assert response.status_code == 200
    assert StockBalance.objects.get().on_hand == 3
    assert InventoryMovement.objects.count() == 2
    assert any('0' in str(message) and '1' in str(message) for message in response.context['messages'])


@pytest.mark.parametrize('action', ['receive', 'adjust'])
def test_unconfigured_is_not_implicitly_initialized(client, owner, variant, action):
    from web.staff.inventory_workspace.intents import issue_intent

    client.force_login(owner)
    data = {f'{action}-intent': issue_intent(owner, variant.pk, action, 0),
        f'{action}-quantity': 2, f'{action}-reason': 'Delivery'}
    assert client.post(command(variant, action), data).status_code == 409
    assert not StockBalance.objects.exists()


def test_safe_localized_database_failure_keeps_retryable_intent(client, owner, variant):
    client.force_login(owner)
    data = payload(client, variant, 'initialize')
    with patch('web.staff.inventory_workspace.command_view.services.initialize',
            side_effect=OperationalError('private-database-name password=secret')):
        response = client.post(command(variant, 'initialize'), data)
    assert response.status_code == 503
    assert 'private-database-name' not in response.content.decode()
    assert response.context['inventory_forms']['initialize'].data['initialize-intent'] == data['initialize-intent']
    assert client.post(command(variant, 'initialize'), data).status_code == 302


@pytest.mark.parametrize('language', ['ru', 'de'])
def test_inventory_locales_cover_forms_errors_and_history(client, owner, variant, language):
    from web.localization import translate_text

    client.force_login(owner)
    with override(language):
        url = detail(variant)
        response = client.get(url)
        assert translate_text('staff.inventory.action.initialize') in response.content.decode()
        assert '[staff.inventory.' not in response.content.decode()
        data = {'initialize-intent': 'bad', 'initialize-quantity': 3, 'initialize-reason': 'Count'}
        response = client.post(command(variant, 'initialize'), data)
        assert response.status_code == 400
        assert translate_text('staff.inventory.error.intent') in response.content.decode()
        initialize(owner, variant)
        html = client.get(url, {'section': 'history'}).content.decode()
        assert translate_text('staff.inventory.action.initialize') in html
        assert '[staff.inventory.' not in html


def test_reconciliation_detects_corruption_without_writing_and_is_permission_scoped(client, owner, variant):
    from web.staff.inventory_workspace.selectors import reconciliation

    initialize(owner, variant)
    with CaptureQueriesContext(connection) as queries:
        assert reconciliation(variant.pk)['matches']
    assert len(queries) == 1
    # Trusted SQL simulates corruption; no application repair is permitted.
    with connection.cursor() as cursor:
        cursor.execute('UPDATE inventory_stockbalance SET on_hand = 11 WHERE variant_id = %s', [variant.pk])
    client.force_login(owner)
    response = client.get(detail(variant))
    assert not response.context['reconciliation']['matches']
    assert StockBalance.objects.get().on_hand == 11
    client.force_login(staff('view_stockbalance'))
    assert 'reconciliation' not in client.get(detail(variant)).context


def test_paginated_selectors_have_two_queries_at_one_and_many_rows(owner, variant):
    from web.staff.inventory_workspace.selectors import (
        bounded_page,
        history_rows,
        reconciliation,
        reservation_rows,
        variants,
    )

    with CaptureQueriesContext(connection) as queries:
        assert reconciliation(variant.pk)['matches']
    assert len(queries) == 1
    initialize(owner, variant, 50)
    for count in (1, 26):
        for index in range(count):
            services.reserve(actor=owner, variant_id=variant.pk, quantity=1,
                reservation_id=f'budget-hold-{count}-{index}', expires_at=timezone.now() + timedelta(minutes=10), now=timezone.now(),
                context=OperationContext(f'budget-hold-{count}-{index}', 'staff', str(owner.pk), 'Hold',
                    StockBalance.objects.get().revision))
        for rows in (variants(), history_rows(variant.pk), reservation_rows(variant.pk)):
            with CaptureQueriesContext(connection) as queries:
                page = bounded_page(rows, '999999999999999')
                assert len(list(page)) <= 25
            assert len(queries) == 2
            assert page.start_index() <= 10001
        with CaptureQueriesContext(connection) as queries:
            rows = list(history_rows(variant.pk)[:25])
            assert all(row.actor.username and row.variant.sku for row in rows)
        assert len(queries) == 1
        with CaptureQueriesContext(connection) as queries:
            list(reservation_rows(variant.pk)[:25])
        assert len(queries) == 1
