import pytest
from codex_django.cabinet.quick_access import get_staff_quick_access_candidates
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse

from web.staff.models import CabinetPreferences

pytestmark = pytest.mark.django_db


def make_user(*, staff=False, owner=False):
    return get_user_model().objects.create_user(username="staff-test", password="test-only-long-password",
                                               is_staff=staff, is_superuser=owner)


def test_anonymous_redirect_and_customer_forbidden(client):
    response = client.get(reverse("staff:home"))
    assert response.status_code == 302
    assert response.url.startswith(reverse("account_login"))
    client.force_login(make_user())
    assert client.get(reverse("staff:home")).status_code == 403
    assert client.get(reverse("staff:settings")).status_code == 403


def test_staff_shell_has_groups_settings_and_no_get_writes(client):
    client.force_login(make_user(staff=True, owner=True))
    response = client.get(reverse("staff:products"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "Shop" in html and "Verwaltung" in html
    assert "Bereichseinstellungen" in html and "Shop-Einstellungen" in html
    assert 'data-staff-settings' in html
    assert CabinetPreferences.objects.count() == 0


def test_quick_access_persists_and_rejects_unknown_keys(client):
    client.force_login(make_user(staff=True, owner=True))
    groups = get_staff_quick_access_candidates()
    key = next(item["key"] for group in groups for item in group["items"] if group["module"] == "catalog")
    state = client.get(reverse("staff:settings")).context["form"]["state"].value()
    response = client.post(reverse("staff:settings"), {"links": [key], "state": state})
    assert response.status_code == 302
    assert CabinetPreferences.objects.get(pk=1).quick_access_keys == [key]
    response = client.get(reverse("staff:home"))
    assert len(response.context["cabinet_quick_access"]) == 1
    assert client.post(reverse("staff:settings"), {"links": ["forged-key"]}).status_code == 400
    assert CabinetPreferences.objects.get(pk=1).quick_access_keys == [key]


def test_saved_quick_access_never_bypasses_permissions(client):
    user = make_user(staff=True)
    key = next(item["key"] for group in get_staff_quick_access_candidates()
               for item in group["items"] if group["module"] == "catalog")
    CabinetPreferences.objects.create(quick_access_keys=[key])
    client.force_login(user)
    response = client.get(reverse("staff:home"))
    assert response.status_code == 200
    assert response.context["cabinet_quick_access"] == []
    assert reverse("staff:products") not in response.content.decode()
    assert client.get(reverse("staff:products")).status_code == 403
    assert client.post(reverse("staff:settings"), {"links": []}).status_code == 403


def test_global_settings_post_requires_csrf():
    client = Client(enforce_csrf_checks=True)
    client.force_login(make_user(staff=True, owner=True))
    assert client.post(reverse("staff:settings"), {"links": []}).status_code == 403


def test_catalog_view_permission_does_not_grant_global_settings(client):
    user = make_user(staff=True)
    user.user_permissions.add(Permission.objects.get(codename="view_product", content_type__app_label="catalog"))
    client.force_login(user)
    assert client.get(reverse("staff:products")).status_code == 200
    assert client.get(reverse("staff:catalog_settings")).status_code == 200
    assert client.get(reverse("staff:settings")).status_code == 403


def test_staff_login_alias_uses_common_login(client):
    response = client.get(reverse("staff:login"))
    assert response.status_code == 302
    assert response.url == reverse("account_login")
    client.force_login(make_user(staff=True))
    assert client.get(reverse("staff:logout")).status_code == 405
    assert client.post(reverse("staff:logout")).status_code == 302
