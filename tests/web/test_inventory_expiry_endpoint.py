import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory, override_settings

from web.inventory.endpoint import expire_due

TOKEN = 'x' * 32


def request(body=b'{}', token=TOKEN, method='post'):
    return getattr(RequestFactory(), method)('/internal/inventory/expiry/', data=body,
        content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {token}')


@pytest.mark.django_db
@override_settings(INVENTORY_EXPIRY_ENABLED=True, INVENTORY_EXPIRY_TOKEN=TOKEN,
    INVENTORY_EXPIRY_BATCH_SIZE=10)
def test_endpoint_uses_configured_actor_and_server_time(settings):
    actor = get_user_model().objects.create_user(username='expiry', is_staff=True, is_superuser=True)
    settings.INVENTORY_EXPIRY_ACTOR_ID = actor.pk
    from web.inventory.expiry_service import ExpirySummary
    with patch('web.inventory.endpoint.expire_due_reservations', return_value=ExpirySummary(3, 2, 1, False)) as call:
        response = expire_due(request())
    assert response.status_code == 200
    assert json.loads(response.content) == {'scanned': 3, 'expired': 2, 'skipped': 1, 'has_more': False}
    assert call.call_args.kwargs['actor'].pk == actor.pk
    assert call.call_args.kwargs['now'].utcoffset().total_seconds() == 0
    assert call.call_args.kwargs['batch_size'] == 10
    assert 'no-store' in response['Cache-Control']


@pytest.mark.django_db
@override_settings(INVENTORY_EXPIRY_ENABLED=True, INVENTORY_EXPIRY_TOKEN=TOKEN)
@pytest.mark.parametrize(('body', 'token', 'status'), [
    (b'{}', 'wrong', 403), (b'{"actor":1}', TOKEN, 400), (b'[]', TOKEN, 400),
    (b' ' * 9000, TOKEN, 413), (b'{', TOKEN, 400),
])
def test_rejects_bad_requests_before_service(body, token, status):
    with patch('web.inventory.endpoint.expire_due_reservations') as call:
        response = expire_due(request(body, token))
    assert response.status_code == status
    assert 'no-store' in response['Cache-Control']
    call.assert_not_called()


@override_settings(INVENTORY_EXPIRY_ENABLED=False)
def test_disabled_and_method():
    assert expire_due(request()).status_code == 404
    with override_settings(INVENTORY_EXPIRY_ENABLED=True):
        response = expire_due(RequestFactory().get('/internal/inventory/expiry/'))
    assert response.status_code == 405
    assert 'no-store' in response['Cache-Control']


@pytest.mark.django_db
@override_settings(INVENTORY_EXPIRY_ENABLED=True, INVENTORY_EXPIRY_TOKEN=TOKEN)
def test_staff_session_cannot_replace_bearer_and_bad_actor_is_safe(client, settings):
    actor = get_user_model().objects.create_user(username='logged-in', is_staff=True, is_superuser=True)
    client.force_login(actor)
    settings.INVENTORY_EXPIRY_ACTOR_ID = actor.pk
    with patch('web.inventory.endpoint.expire_due_reservations') as call:
        response = client.post('/internal/inventory/expiry/', data='{}', content_type='application/json')
    assert response.status_code == 403
    call.assert_not_called()
    settings.INVENTORY_EXPIRY_ACTOR_ID = 999999999
    response = client.post('/internal/inventory/expiry/', data='{}', content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {TOKEN}')
    assert response.status_code == 503
    assert json.loads(response.content) == {'error': 'unavailable'}


@pytest.mark.django_db
@override_settings(INVENTORY_EXPIRY_ENABLED=True, INVENTORY_EXPIRY_TOKEN=TOKEN)
def test_service_errors_are_generic(client, settings):
    actor = get_user_model().objects.create_user(username='expiry-error', is_staff=True, is_superuser=True)
    settings.INVENTORY_EXPIRY_ACTOR_ID = actor.pk
    with patch('web.inventory.endpoint.expire_due_reservations', side_effect=RuntimeError('secret sql')):
        response = client.post('/internal/inventory/expiry/', data='', content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {TOKEN}')
    assert response.status_code == 503
    assert b'secret' not in response.content
    assert 'no-store' in response['Cache-Control']
