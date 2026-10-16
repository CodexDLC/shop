import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse

from web.customer.models import CustomerAddress

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner(client):
    user = get_user_model().objects.create_user(username="address-owner", email="owner@example.test")
    client.force_login(user)
    return user


def standard(**changes):
    data = {"kind": "standard", "recipient": "Max Muster", "street_address": "Musterstraße 12a",
            "postal_code": "10115", "city": "Berlin", "country": "DE"}
    return data | changes


def packstation(**changes):
    return standard(kind="packstation", street_address="", post_number="123456789", station_number="123") | changes


def create(client, **data):
    return client.post(reverse("customer:address_create"), standard(**data))


def test_profile_saves_single_display_name_without_changing_auth(owner, client):
    owner.last_name = "Old surname"
    owner.save()
    response = client.post(reverse("customer:save_profile"), {
        "display_name": "  Max von Muster  ", "email": "attacker@example.test", "is_staff": "true",
    })
    assert response.status_code == 302
    assert response.url == reverse("customer:profile") + "#tab-profile"
    owner.refresh_from_db()
    assert owner.first_name == "Max von Muster"
    assert owner.last_name == ""
    assert owner.email == "owner@example.test"
    assert not owner.is_staff
    assert client.get(reverse("customer:overview")).context["customer_display_name"] == "Max von Muster"


@pytest.mark.parametrize("name", ["", "   ", "x" * 151])
def test_invalid_profile_returns_bound_form_without_writing(owner, client, name):
    response = client.post(reverse("customer:save_profile"), {"display_name": name})
    assert response.status_code == 400
    assert response.context["profile_form"].errors["display_name"]
    assert response.context["active_tab"] == "tab-profile"
    owner.refresh_from_db()
    assert owner.first_name == ""


def test_standard_address_persists_owner_and_initial_default(owner, client):
    response = create(client, user="9999", is_staff="true", post_number="123456789", station_number="123")
    assert response.status_code == 302
    address = CustomerAddress.objects.get()
    assert address.user_id == owner.pk
    assert address.recipient == "Max Muster"
    assert address.street_address == "Musterstraße 12a"
    assert address.post_number == address.station_number == ""
    assert address.is_default
    context = client.get(reverse("customer:profile")).context
    assert context["customer_addresses"] == [address]
    assert context["customer_default_address"] == address
    assert context["customer_address_data"][0]["recipient"] == address.recipient
    assert "user_id" not in context["customer_address_data"][0]


def test_packstation_persists_and_clears_street(owner, client):
    response = client.post(reverse("customer:address_create"), packstation(street_address="Discard street 10"))
    assert response.status_code == 302
    address = CustomerAddress.objects.get()
    assert address.kind == "packstation"
    assert address.post_number == "123456789"
    assert address.station_number == "123"
    assert address.street_address == ""


@pytest.mark.parametrize(("changes", "field"), [
    ({"postal_code": "1234"}, "postal_code"),
    ({"postal_code": "１２３４５"}, "postal_code"),
    ({"postal_code": "12A45"}, "postal_code"),
    ({"country": "AT"}, "country"),
    ({"country": "CH"}, "country"),
    ({"kind": "unknown"}, "kind"),
    ({"street_address": "Musterstraße"}, "street_address"),
    ({"street_address": "12"}, "street_address"),
    ({"street_address": ""}, "street_address"),
    ({"recipient": ""}, "recipient"),
    ({"recipient": "1234"}, "recipient"),
    ({"city": "Ber\nlin"}, "city"),
    ({"city": "x" * 101}, "city"),
])
def test_address_validation_renders_existing_reference_and_bound_form(owner, client, changes, field):
    response = client.post(reverse("customer:address_create"), standard(**changes))
    assert response.status_code == 400
    assert response.context["address_form"].errors[field]
    assert response.context["address_form"].is_bound
    assert response.context["address_modal_open"] is True
    assert response.context["active_tab"] == "tab-addresses"
    assert CustomerAddress.objects.count() == 0


@pytest.mark.parametrize(("changes", "field"), [
    ({"post_number": "12345"}, "post_number"),
    ({"post_number": "12345678901"}, "post_number"),
    ({"post_number": "12ABC678"}, "post_number"),
    ({"station_number": ""}, "station_number"),
    ({"station_number": "123456"}, "station_number"),
])
def test_packstation_validation(owner, client, changes, field):
    response = client.post(reverse("customer:address_create"), packstation(**changes))
    assert response.status_code == 400
    assert field in response.context["address_form"].errors
    assert not CustomerAddress.objects.exists()


def test_create_update_default_and_delete_transitions(owner, client):
    create(client)
    first = CustomerAddress.objects.get()
    create(client, recipient="Other Muster")
    second = CustomerAddress.objects.exclude(pk=first.pk).get()
    assert not second.is_default
    response = client.post(reverse("customer:address_update", args=[second.pk]), standard(
        recipient="Updated Muster", is_default="on"))
    assert response.status_code == 302
    first.refresh_from_db()
    second.refresh_from_db()
    assert not first.is_default and second.is_default
    assert second.recipient == "Updated Muster"
    # Unchecking the only default cannot leave an address book without a default.
    client.post(reverse("customer:address_update", args=[second.pk]), standard(recipient="Updated Muster"))
    second.refresh_from_db()
    assert second.is_default
    client.post(reverse("customer:address_default", args=[first.pk]))
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.is_default and not second.is_default
    client.post(reverse("customer:address_delete", args=[first.pk]))
    second.refresh_from_db()
    assert second.is_default
    client.post(reverse("customer:address_delete", args=[second.pk]))
    assert not CustomerAddress.objects.exists()


@pytest.mark.parametrize("route", ["address_update", "address_delete", "address_default"])
def test_other_owner_address_not_found_even_for_staff(owner, client, route):
    another = get_user_model().objects.create_user(username="another-address-owner")
    address = CustomerAddress.objects.create(user=another, **standard(), is_default=True)
    owner.is_staff = True
    owner.save()
    response = client.post(reverse("customer:" + route, args=[address.pk]), standard(recipient="Attack Muster"))
    assert response.status_code == 404
    address.refresh_from_db()
    assert address.recipient == "Max Muster" and address.user_id == another.pk


def test_invalid_update_keeps_old_address_and_edit_id(owner, client):
    create(client)
    address = CustomerAddress.objects.get()
    response = client.post(reverse("customer:address_update", args=[address.pk]), standard(postal_code="BAD"))
    assert response.status_code == 400
    assert response.context["address_edit_id"] == address.pk
    address.refresh_from_db()
    assert address.postal_code == "10115"


@pytest.mark.parametrize("route", ["save_profile", "address_create", "address_update", "address_delete", "address_default"])
def test_mutations_require_login_post_and_csrf(owner, client, route):
    args = [123] if route in ("address_update", "address_delete", "address_default") else []
    url = reverse("customer:" + route, args=args)
    assert client.get(url).status_code == 405
    anonymous = Client()
    assert anonymous.post(url, {}).status_code == 302
    secure = Client(enforce_csrf_checks=True)
    secure.force_login(owner)
    assert secure.post(url, standard()).status_code == 403


def test_database_rejects_two_defaults_for_same_customer(owner):
    CustomerAddress.objects.create(user=owner, **standard(), is_default=True)
    with pytest.raises(IntegrityError), transaction.atomic():
        CustomerAddress.objects.create(user=owner, **standard(), is_default=True)


def test_other_customer_can_have_own_default(owner):
    other = get_user_model().objects.create_user(username="other-default")
    CustomerAddress.objects.create(user=owner, **standard(), is_default=True)
    CustomerAddress.objects.create(user=other, **standard(), is_default=True)
    assert CustomerAddress.objects.filter(is_default=True).count() == 2


def test_name_rejects_embedded_control_characters(owner, client):
    response = client.post(reverse("customer:save_profile"), {"display_name": "Max\nMuster"})
    assert response.status_code == 400
    owner.refresh_from_db()
    assert owner.first_name == ""
