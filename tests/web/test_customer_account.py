from datetime import datetime, timezone
from html.parser import HTMLParser

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.html import escape

pytestmark = pytest.mark.django_db


class AccountPageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = set()
        self.tags = set()
        self.forms = []
        self.password_fields = []
        self.visible_parts = []
        self.input_values = []
        self.hidden_depth = 0
        self.disabled_fieldsets = []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag)
        attributes = dict(attrs)
        if tag in {"script", "style"}:
            self.hidden_depth += 1
        if tag == "input":
            self.input_values.append(attributes.get("value", ""))
        if tag == "fieldset":
            self.disabled_fieldsets.append("disabled" in attributes)
        if tag == "form":
            self.forms.append(attributes)
        if tag == "input" and attributes.get("type") == "password":
            self.password_fields.append("disabled" in attributes or any(self.disabled_fieldsets))
        if tag == "a" and "href" in attributes:
            self.links.add(attributes["href"])

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden_depth -= 1
        if tag == "fieldset":
            self.disabled_fieldsets.pop()

    def handle_data(self, data):
        if not self.hidden_depth:
            self.visible_parts.append(data)


@pytest.fixture
def customer():
    return get_user_model().objects.create_user(
        username="reference-customer",
        email="reference-customer@example.test",
        password="Example-Password-Only!852",
        first_name='<script>alert("name")</script>',
        last_name="Example & Customer",
        date_joined=datetime(2021, 6, 5, tzinfo=timezone.utc),
    )


@pytest.mark.parametrize("route", ["customer:overview", "customer:profile"])
def test_customer_reference_requires_the_common_login(client, route):
    response = client.get(reverse(route))
    assert response.status_code == 302
    assert response.url == f"{reverse('account_login')}?next={reverse(route)}"


@pytest.mark.parametrize("route", ["customer:overview", "customer:profile"])
def test_customer_reference_uses_current_identity_and_escapes_it(client, customer, route):
    client.force_login(customer)
    response = client.get(reverse(route))
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store, private"
    html = response.content.decode()
    assert str(escape(customer.get_full_name())) in html
    assert customer.email in html
    assert "2021" in html
    assert customer.first_name not in html
    parser = AccountPageParser()
    parser.feed(html)
    rendered_identity = " ".join(parser.visible_parts + parser.input_values)
    assert "Maximilian von Bergmann" not in rendered_identity
    assert "maximilian.v@atelier-muenchen.de" not in rendered_identity
    assert "Kundennr. MM-84920" not in rendered_identity
    assert "data-customer-reference" in html
    assert "data-customer-demo" in html
    assert response.context["customer_display_name"] == customer.get_full_name()


def test_customer_reference_falls_back_to_username_without_a_name(client, customer):
    customer.first_name = ""
    customer.last_name = ""
    customer.save(update_fields=["first_name", "last_name"])
    client.force_login(customer)
    response = client.get(reverse("customer:overview"))
    assert response.context["customer_display_name"] == customer.username
    assert customer.username in response.content.decode()


@pytest.mark.parametrize("route", ["customer:overview", "customer:profile"])
def test_customer_reference_keeps_navigation_and_real_security_actions(client, customer, route):
    client.force_login(customer)
    html = client.get(reverse(route)).content.decode()
    parser = AccountPageParser()
    parser.feed(html)
    assert "aside" in parser.tags
    assert "nav" in parser.tags
    assert "data-account-security" in html
    for name in ("account_change_password", "account_email", "mfa_index", "account_logout"):
        assert reverse(name) in parser.links
    assert reverse("customer:overview") in parser.links
    assert reverse("customer:profile") in {link.split("#")[0] for link in parser.links}


def test_overview_retains_the_reference_kpi_and_order_composition(client, customer):
    client.force_login(customer)
    html = client.get(reverse("customer:overview")).content.decode()
    assert "md:grid-cols-3" in html
    assert "MM-849204" in html
    assert "data-demo-page=\"account.html\"" in html
    assert "Designvorschau" in html


def test_profile_mock_cannot_change_identity_or_password(client, customer):
    client.force_login(customer)
    original_password = customer.password
    response = client.post(reverse("customer:profile"), {
        "email": "attacker@example.test",
        "first_name": "Different Person",
        "password": "Changed-Password-123!",
        "is_staff": "true",
    })
    assert response.status_code == 405
    customer.refresh_from_db()
    assert customer.email == "reference-customer@example.test"
    assert customer.first_name == '<script>alert("name")</script>'
    assert customer.password == original_password
    assert not customer.is_staff


def test_profile_demo_forms_do_not_claim_real_saves_or_accept_passwords(client, customer):
    client.force_login(customer)
    html = client.get(reverse("customer:profile")).content.decode()
    parser = AccountPageParser()
    parser.feed(html)
    assert parser.forms
    assert parser.password_fields
    assert all(parser.password_fields)
    for form in parser.forms:
        submit_script = form.get("onsubmit", "")
        assert "erfolgreich aktualisiert" not in submit_script
        assert "erfolgreich gespeichert" not in submit_script
        assert "Daten gespeichert" not in submit_script
