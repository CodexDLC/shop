import pytest
from django.contrib.auth.models import Permission
from django.core import signing
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse

from tests.web.test_staff_operations import staff_user
from web.cart.models import PromoCode
from web.localization import translate_text
from web.staff.models import StaffAuditEvent
from web.staff.operations.editing import issue_state
from web.staff.operations.promo_form import PromoForm
from web.support.models import ContactTicket

pytestmark = pytest.mark.django_db


def promo_data(**overrides):
    return {"code": "STAFF10", "kind": "percent", "value": "10.00", "min_subtotal": "20.00",
            "currency": "EUR", "is_active": "on", "starts_at": "", "ends_at": "",
            "original_state": issue_state("cart.promocode"), **overrides}


def ticket_record(**overrides):
    return ContactTicket.objects.create(name="Buyer", email="buyer@example.test", topic="versand",
                                         message="Where is the parcel?", **overrides)


def test_promo_create_edit_real_values_and_audit(client):
    user = staff_user("cart.view_promocode", "cart.add_promocode", "cart.change_promocode")
    client.force_login(user)
    add = reverse("staff:promo_add")
    assert client.get(add).status_code == 200
    assert PromoCode.objects.count() == 0
    response = client.post(add, promo_data())
    assert response.status_code == 302
    promo = PromoCode.objects.get(code="STAFF10")
    assert promo.is_active and promo.value == 10
    assert StaffAuditEvent.objects.get().action == "promo.created"
    edit = reverse("staff:promo_edit", kwargs={"pk": promo.pk})
    token = client.get(edit).context["form"].initial["original_state"]
    response = client.post(edit, promo_data(value="15.00", original_state=token))
    assert response.status_code == 302
    promo.refresh_from_db()
    assert promo.value == 15
    assert list(StaffAuditEvent.objects.values_list("action", flat=True)) == ["promo.updated", "promo.created"]
    # Replay of a prior state cannot silently overwrite the saved value.
    assert client.post(edit, promo_data(value="18.00", original_state=token)).status_code == 409
    promo.refresh_from_db()
    assert promo.value == 15 and StaffAuditEvent.objects.count() == 2


@pytest.mark.parametrize("overrides", [
    {"value": "101"}, {"value": "0"}, {"min_subtotal": "-1"}, {"kind": "unknown"},
    {"currency": "USD"}, {"code": "lower-case"},
    {"starts_at": "2026-10-22T12:00", "ends_at": "2026-10-21T12:00"},
    {"code": "<script>"},
])
def test_invalid_promo_never_creates_record_or_audit(client, overrides):
    client.force_login(staff_user("cart.view_promocode", "cart.add_promocode"))
    response = client.post(reverse("staff:promo_add"), promo_data(**overrides))
    assert response.status_code == 400
    assert not PromoCode.objects.exists() and not StaffAuditEvent.objects.exists()
    assert 'value="<script>"' not in response.content.decode()
    if overrides.get("code") == "<script>":
        assert 'value="&lt;script&gt;"' in response.content.decode()


def test_promo_unique_and_state_model_id_signature_and_expiration(client, monkeypatch):
    client.force_login(staff_user("cart.view_promocode", "cart.add_promocode", "cart.change_promocode"))
    first = PromoCode.objects.create(code="FIRST", kind="percent", value=10)
    second = PromoCode.objects.create(code="SECOND", kind="fixed", value=5)
    edit = reverse("staff:promo_edit", kwargs={"pk": second.pk})
    assert client.post(edit, promo_data(original_state=issue_state("cart.promocode", first))).status_code == 409
    assert client.post(edit, promo_data(original_state="forged")).status_code == 409
    assert client.post(reverse("staff:promo_add"), promo_data(code="FIRST")).status_code == 400
    token = issue_state("cart.promocode", second)
    monkeypatch.setattr(signing.time, "time", lambda: 9999999999)
    assert client.post(edit, promo_data(original_state=token)).status_code == 409
    assert not StaffAuditEvent.objects.exists()


def test_promo_mutation_requires_view_and_specific_add_or_change(client):
    user = staff_user("cart.view_promocode")
    client.force_login(user)
    promo = PromoCode.objects.create(code="BEFORE", kind="percent", value=10)
    assert client.post(reverse("staff:promo_add"), promo_data()).status_code == 403
    assert client.get(reverse("staff:promo_edit", kwargs={"pk": promo.pk})).status_code == 403
    user.user_permissions.clear()
    user.user_permissions.add(Permission.objects.get(content_type__app_label="cart", codename="add_promocode"))
    assert client.post(reverse("staff:promo_add"), promo_data()).status_code == 403
    assert PromoCode.objects.count() == 1 and not StaffAuditEvent.objects.exists()


def test_support_resolve_reopen_binds_ticket_state_and_never_sends_mail(client, mailoutbox):
    user = staff_user("support.view_contactticket", "support.change_contactticket")
    client.force_login(user)
    ticket = ticket_record()
    other = ticket_record()
    status = reverse("staff:support_status", kwargs={"pk": ticket.pk})
    detail = reverse("staff:support_detail", kwargs={"pk": ticket.pk})
    token = client.get(detail).context["support_state"]
    assert client.get(status).status_code == 405
    assert client.post(reverse("staff:support_status", kwargs={"pk": other.pk}),
                       {"action": "resolve", "original_state": token}).status_code == 409
    assert client.post(status, {"action": "resolve", "original_state": token}).status_code == 302
    ticket.refresh_from_db()
    assert ticket.resolved
    assert client.post(status, {"action": "reopen", "original_state": token}).status_code == 409
    token = client.get(detail).context["support_state"]
    assert client.post(status, {"action": "reopen", "original_state": token}).status_code == 302
    ticket.refresh_from_db()
    assert not ticket.resolved and len(mailoutbox) == 0
    assert list(StaffAuditEvent.objects.values_list("action", flat=True)) == ["support.reopened", "support.resolved"]


def test_support_rejects_invalid_action_stale_message_and_missing_capabilities(client):
    user = staff_user("support.view_contactticket")
    client.force_login(user)
    ticket = ticket_record()
    url = reverse("staff:support_status", kwargs={"pk": ticket.pk})
    token = issue_state("support.contactticket", ticket)
    assert client.post(url, {"action": "resolve", "original_state": token}).status_code == 403
    assert "support_state" not in client.get(reverse("staff:support_detail", kwargs={"pk": ticket.pk})).context
    user.user_permissions.add(Permission.objects.get(content_type__app_label="support", codename="change_contactticket"))
    assert client.post(url, {"action": "delete", "original_state": token}).status_code == 400
    ContactTicket.objects.filter(pk=ticket.pk).update(message="Changed by another operator")
    assert client.post(url, {"action": "resolve", "original_state": token}).status_code == 409
    assert not StaffAuditEvent.objects.exists()


def test_mutations_enforce_csrf_even_with_valid_signed_states():
    client = Client(enforce_csrf_checks=True)
    client.force_login(staff_user(owner=True))
    ticket = ticket_record()
    assert client.post(reverse("staff:promo_add"), promo_data()).status_code == 403
    assert client.post(reverse("staff:support_status", kwargs={"pk": ticket.pk}),
                       {"action": "resolve", "original_state": issue_state("support.contactticket", ticket)}).status_code == 403
    assert not StaffAuditEvent.objects.exists() and not PromoCode.objects.exists()


@pytest.mark.parametrize("overrides,field,key", [
    ({"value": "150"}, "value", "percent"),
    ({"value": "0"}, "value", "percent"),
    ({"kind": "fixed", "value": "0"}, "value", "positive"),
    ({"code": "lower-case"}, "code", "code"),
    ({"currency": "USD"}, "currency", "currency"),
    ({"starts_at": "2026-10-22T12:00", "ends_at": "2026-10-21T12:00"}, "ends_at", "date_order"),
    ({"min_subtotal": "-1"}, "min_subtotal", "minimum"),
    ({"value": "not a number"}, "value", "number"),
    ({"value": ""}, "value", "required"),
    ({"starts_at": "invalid date"}, "starts_at", "date"),
    ({"kind": "unknown"}, "kind", "kind"),
])
def test_promo_errors_identify_field_and_recovery_without_duplicate_generic_feedback(overrides, field, key):
    form = PromoForm(promo_data(**overrides))
    assert not form.is_valid()
    assert dict(form.errors) == {field: [translate_text(f"staff.records.promo_error.{key}")]}


def test_duplicate_promo_code_has_specific_field_message():
    PromoCode.objects.create(code="STAFF10", kind="percent", value=10)
    form = PromoForm(promo_data())
    assert not form.is_valid()
    assert dict(form.errors) == {"code": [translate_text("staff.records.promo_error.duplicate")]}


def test_promo_model_clean_stays_authoritative_for_unrecognized_failures(monkeypatch):
    def reject(self):
        raise ValidationError("Future domain rule rejected the code")

    monkeypatch.setattr(PromoCode, "clean", reject)
    form = PromoForm(promo_data())
    assert not form.is_valid()
    assert dict(form.errors) == {"__all__": [translate_text("staff.records.promo_error.invalid")]}
