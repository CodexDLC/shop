import pytest
from django.test import override_settings
from django.urls import reverse


@pytest.mark.django_db
def test_real_404_uses_reference_recovery_and_working_catalog_search(client):
    with override_settings(DEBUG=False):
        response = client.get('/missing-page-for-recovery-test/')
    assert response.status_code == 404
    html = response.content.decode()
    assert 'data-demo-page="404.html"' in html
    assert f'action="{reverse("catalog:search")}"' in html
    assert 'name="q"' in html
    assert 'Page not found at' not in html
