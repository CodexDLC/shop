import pytest
from django.contrib.auth.models import Permission
from django.db import IntegrityError, transaction
from django.test import Client, RequestFactory
from django.urls import resolve, reverse
from django.utils.translation import override

from web.shop.identity import PUBLIC_FIELDS, get_store_identity
from web.shop.models import StoreIdentity
from web.staff.models import StaffAuditEvent
from web.staff.views.store_identity_view import StoreIdentityView

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner(client, django_user_model):
    user = django_user_model.objects.create_superuser(username="identity-owner", password="test-only")
    client.force_login(user)
    return client


def url():
    return reverse("staff:workspace_preview", kwargs={"section": "store_settings"})


def token(client):
    return client.get(url()).context["form"]["state"].value()


def payload(state, **changes):
    values = dict.fromkeys(PUBLIC_FIELDS, "")
    values.update(legal_name="QA Shop GmbH", street_address="Testweg 2", postal_code="10115", city="Berlin",
                  country="DE", contact_email="public@example.test", contact_phone="+49 (30) 123-456", state=state)
    values.update(changes)
    return values


def test_route_dispatch_and_get_does_not_create(owner):
    assert resolve(url()).func.view_class is StoreIdentityView
    for lang in ["ru", "de"]:
        with override(lang):
            response = owner.get(url())
            assert response.status_code == 200
            assert "noindex" in response["X-Robots-Tag"]
            assert 'type="submit"' in response.content.decode()
            assert len(response.context["settings_cards"]) == 3
    assert not StoreIdentity.objects.exists()


def test_saved_identity_is_public_without_revision_or_actor(owner):
    assert owner.post(url(), payload(token(owner))).status_code == 302
    saved = StoreIdentity.objects.get()
    assert saved.revision == 1
    public = get_store_identity()
    assert set(public) == set(PUBLIC_FIELDS) | {"phone_href", "email_href"}
    assert public["legal_name"] == "QA Shop GmbH"
    assert public["phone_href"] == "tel:+4930123456"
    assert public["email_href"] == "mailto:public@example.test"
    event = StaffAuditEvent.objects.get(action="store_identity.updated")
    assert event.object_type == "shop.storeidentity"


@pytest.mark.parametrize("changes", [{"contact_email": "bad"}, {"legal_name": " "}, {"city": ""},
    {"postal_code": "1234"}, {"country": "US"}, {"contact_phone": "javascript:alert(1)"}])
def test_invalid_settings_never_save(owner, changes):
    assert owner.post(url(), payload(token(owner), **changes)).status_code == 400
    assert not StoreIdentity.objects.exists()
    assert not StaffAuditEvent.objects.exists()


@pytest.mark.parametrize("existing", [True, False])
def test_stale_and_replay_forms_do_not_overwrite(owner, existing):
    if existing:
        StoreIdentity.objects.create(**{k:v for k,v in payload("").items() if k != "state"})
    stale = token(owner)
    assert owner.post(url(), payload(stale)).status_code == 302
    assert owner.post(url(), payload(stale, legal_name="Overwrite")).status_code == 409
    assert StoreIdentity.objects.get().legal_name == "QA Shop GmbH"
    assert StaffAuditEvent.objects.count() == 1


def test_same_revision_external_change_rejected(owner):
    assert owner.post(url(), payload(token(owner))).status_code == 302
    stale = token(owner)
    StoreIdentity.objects.update(city="Hamburg")
    assert owner.post(url(), payload(stale)).status_code == 409
    assert StoreIdentity.objects.get().city == "Hamburg"


def test_signed_state_bound_to_actor(owner, django_user_model, client):
    state = token(owner)
    user = django_user_model.objects.create_superuser(username="second-owner")
    client.force_login(user)
    assert client.post(url(), payload(state)).status_code == 409
    assert not StoreIdentity.objects.exists()


def test_save_requires_explicit_permission_not_quick_access(client, django_user_model):
    user = django_user_model.objects.create_user(username="quick-only", is_staff=True)
    user.user_permissions.add(Permission.objects.get(codename="change_cabinetpreferences"))
    client.force_login(user)
    assert client.get(url()).status_code == 403
    assert client.post(url(), payload("bad")).status_code == 403
    user.user_permissions.add(Permission.objects.get(codename="change_storeidentity"))
    assert client.get(url()).status_code == 200
    assert client.post(url(), payload(token(client))).status_code == 302


def test_csrf_enforced(owner):
    client = Client(enforce_csrf_checks=True)
    # Use the already authenticated session with strict CSRF checking.
    client.cookies = owner.cookies
    assert client.post(url(), payload(token(owner))).status_code == 403


@pytest.mark.parametrize("existing", [True, False])
def test_audit_failure_rolls_back_identity(owner, monkeypatch, existing):
    if existing:
        StoreIdentity.objects.create(**{k:v for k,v in payload("").items() if k != "state"})
    def fail(*args):
        raise RuntimeError("audit unavailable")
    state = token(owner)
    monkeypatch.setattr("web.staff.services.store_identity.record_staff_action", fail)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        owner.post(url(), payload(state, city="Hamburg"))
    if existing:
        assert StoreIdentity.objects.get().city == "Berlin"
    else:
        assert not StoreIdentity.objects.exists()


def test_public_read_empty_and_memoized(django_assert_num_queries):
    request = RequestFactory().get("/")
    with django_assert_num_queries(1):
        public = get_store_identity(request)
        public["legal_name"] = "should not affect memo"
        assert get_store_identity(request)["legal_name"] == ""
    assert public["phone_href"] == public["email_href"] == ""
    assert not StoreIdentity.objects.exists()


def test_corrupt_phone_never_produces_unsafe_link():
    StoreIdentity.objects.create(contact_phone="javascript:alert(1)")
    assert get_store_identity()["phone_href"] == ""


def test_singleton_database_constraint():
    with pytest.raises(IntegrityError), transaction.atomic():
        StoreIdentity.objects.create(pk=2)
