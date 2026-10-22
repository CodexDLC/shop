import pytest
from codex_django.cabinet.quick_access import get_staff_quick_access_candidates
from django.contrib.auth.models import Permission
from django.db import IntegrityError
from django.db.models.query import QuerySet
from django.test import Client
from django.urls import reverse
from django.utils.translation import override

from web.staff.models import CabinetPreferences, StaffAuditEvent

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def german():
    with override("de"):
        yield


@pytest.fixture
def owner(client, django_user_model):
    account = django_user_model.objects.create_superuser(username="settings-owner", password="test-only")
    client.force_login(account)
    return client


def state(client):
    return client.get(reverse("staff:settings")).context["form"]["state"].value()


def candidates(module):
    return next(group["items"] for group in get_staff_quick_access_candidates() if group["module"] == module)


def test_limited_editor_preserves_hidden_pins_and_shared_scope(client, django_user_model):
    hidden = candidates("catalog")[0]["key"]
    visible = candidates("management")[0]["key"]
    preferences = CabinetPreferences.objects.create(quick_access_keys=[hidden, visible])
    account = django_user_model.objects.create_user(username="settings-only", is_staff=True)
    account.user_permissions.add(Permission.objects.get(content_type__app_label="staff", codename="change_cabinetpreferences"))
    client.force_login(account)
    response = client.get(reverse("staff:settings"))
    assert hidden not in dict(response.context["form"].fields["links"].choices)
    response = client.post(reverse("staff:settings"), {"state": state(client), "links": []})
    assert response.status_code == 302
    preferences.refresh_from_db()
    assert preferences.quick_access_keys == [hidden]
    assert preferences.revision == 1
    assert StaffAuditEvent.objects.filter(action="quick_access.updated", actor=account).count() == 1


@pytest.mark.parametrize("existing", [True, False])
def test_stale_submit_never_overwrites_other_save(owner, existing):
    if existing:
        CabinetPreferences.objects.create()
    first = state(owner)
    second = state(owner)
    key = candidates("catalog")[0]["key"]
    assert owner.post(reverse("staff:settings"), {"state": first, "links": [key]}).status_code == 302
    response = owner.post(reverse("staff:settings"), {"state": second, "links": []})
    assert response.status_code == 409
    assert CabinetPreferences.objects.get().quick_access_keys == [key]
    assert StaffAuditEvent.objects.count() == 1
    assert "Aktuelle Auswahl laden" in response.content.decode()


def test_aba_change_and_token_replay_rejected(owner):
    preferences = CabinetPreferences.objects.create()
    stale = state(owner)
    for keys in ([candidates("catalog")[0]["key"]], []):
        assert owner.post(reverse("staff:settings"), {"state": state(owner), "links": keys}).status_code == 302
    assert owner.post(reverse("staff:settings"), {"state": stale, "links": []}).status_code == 409
    preferences.refresh_from_db()
    assert preferences.revision == 2


def test_token_actor_binding_tamper_and_missing(owner, django_user_model):
    old_state = state(owner)
    owner.force_login(django_user_model.objects.create_superuser(username="second-owner", password="test-only"))
    assert owner.post(reverse("staff:settings"), {"state": old_state}).status_code == 409
    assert owner.post(reverse("staff:settings"), {"state": "tampered"}).status_code == 409
    assert owner.post(reverse("staff:settings"), {}).status_code == 400
    assert not CabinetPreferences.objects.exists()
    assert not StaffAuditEvent.objects.exists()


def test_conditional_update_conflict_is_not_a_success(owner, monkeypatch):
    CabinetPreferences.objects.create()
    token = state(owner)
    original_update = QuerySet.update
    def lost_race(queryset, **kwargs):
        if queryset.model is CabinetPreferences:
            return 0
        return original_update(queryset, **kwargs)
    monkeypatch.setattr(QuerySet, "update", lost_race)
    assert owner.post(reverse("staff:settings"), {"state": token}).status_code == 409
    assert CabinetPreferences.objects.get().revision == 0
    assert not StaffAuditEvent.objects.exists()


def test_first_insert_unique_conflict_is_handled_with_working_transaction(owner, monkeypatch):
    token = state(owner)
    original_create = QuerySet.create
    def concurrent_insert(queryset, **kwargs):
        if queryset.model is CabinetPreferences:
            raise IntegrityError("simulated concurrent singleton insertion")
        return original_create(queryset, **kwargs)
    monkeypatch.setattr(QuerySet, "create", concurrent_insert)
    assert owner.post(reverse("staff:settings"), {"state": token}).status_code == 409
    assert not StaffAuditEvent.objects.exists()
    assert not CabinetPreferences.objects.exists()


def test_csrf_required_even_with_valid_signed_state(django_user_model):
    account = django_user_model.objects.create_superuser(username="csrf-settings", password="test-only")
    client = Client(enforce_csrf_checks=True)
    client.force_login(account)
    token = state(client)
    url = reverse("staff:settings")
    assert client.post(url, {"state": token}).status_code == 403
    assert client.post(url, {"state": token, "csrfmiddlewaretoken": client.cookies["csrftoken"].value}).status_code == 302


@pytest.mark.parametrize("lang", ["de", "ru"])
@pytest.mark.parametrize("section", ["catalog", "operations_settings"])
def test_settings_design_clear_typed_readonly_and_no_get_writes(owner, lang, section):
    with override(lang):
        url = reverse("staff:catalog_settings") if section == "catalog" else reverse("staff:workspace_preview", kwargs={"section": section})
        response = owner.get(url)
        assert response.status_code == 200
        html = response.content.decode()
        assert "fieldset disabled" in html
        assert "<select" in html
        assert 'type="submit"' not in html.split('<section class="staff-settings-workspace"')[1]
        assert 'aria-current="page"' in html
        assert "[staff.settings_workspace." not in html
        assert len(response.context["settings_cards"]) >= 3
        assert owner.post(url, {}).status_code == 405
    assert not CabinetPreferences.objects.exists()


def test_catalog_settings_links_respect_resource_permissions(client, django_user_model):
    account = django_user_model.objects.create_user(username="catalog-settings-only", is_staff=True)
    account.user_permissions.add(Permission.objects.get(content_type__app_label="catalog", codename="view_product"))
    client.force_login(account)
    response = client.get(reverse("staff:catalog_settings"))
    links = [link["url"] for card in response.context["settings_cards"] for link in card["links"]]
    assert links == [reverse("staff:products")]
    assert len(response.context["settings_navigation"]) == 1
    assert client.get(reverse("staff:workspace_preview", kwargs={"section": "store_settings"})).status_code == 403


def test_same_revision_external_keys_change_is_rejected(owner):
    preferences = CabinetPreferences.objects.create()
    token = state(owner)
    key = candidates("catalog")[0]["key"]
    CabinetPreferences.objects.filter(pk=preferences.pk).update(quick_access_keys=[key])
    assert owner.post(reverse("staff:settings"), {"state": token}).status_code == 409
    assert CabinetPreferences.objects.get().quick_access_keys == [key]
    assert not StaffAuditEvent.objects.exists()


def test_failed_audit_rolls_back_preferences(owner, monkeypatch):
    token = state(owner)
    def failed_audit(*args):
        raise RuntimeError("audit unavailable")
    monkeypatch.setattr("web.staff.views.quick_access_view.record_staff_action", failed_audit)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        owner.post(reverse("staff:settings"), {"state": token})
    assert not CabinetPreferences.objects.exists()


@pytest.mark.parametrize("remove_visible,append_new", [(False, False), (False, True), (True, True)])
def test_mixed_existing_pin_order_is_retained_and_new_pins_append(
    client, django_user_model, remove_visible, append_new,
):
    hidden = candidates("catalog")[0]["key"]
    visible, new = [item["key"] for item in candidates("management")[:2]]
    preferences = CabinetPreferences.objects.create(quick_access_keys=[visible, hidden])
    account = django_user_model.objects.create_user(username="mixed-pin-editor", is_staff=True)
    account.user_permissions.add(
        Permission.objects.get(content_type__app_label="staff", codename="change_cabinetpreferences"),
        Permission.objects.get(content_type__app_label="cart", codename="view_promocode"),
    )
    client.force_login(account)
    submitted = ([new] if append_new else []) + ([] if remove_visible else [visible])
    response = client.post(reverse("staff:settings"), {"state": state(client), "links": submitted})
    assert response.status_code == 302
    preferences.refresh_from_db()
    expected = ([hidden] if remove_visible else [visible, hidden]) + ([new] if append_new else [])
    assert preferences.quick_access_keys == expected
