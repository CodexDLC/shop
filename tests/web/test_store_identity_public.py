import re

import pytest
from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.translation import override

from web.shop.context_processors import store_identity
from web.shop.identity import PUBLIC_FIELDS
from web.shop.models import StoreIdentity

pytestmark = pytest.mark.django_db


def rendered_body(response):
    return re.sub(r"<script\b[^>]*>.*?</script>", "", response.content.decode(), flags=re.S)


def values(**changes):
    data = dict.fromkeys(PUBLIC_FIELDS, "")
    data.update(legal_name="QA Shop & Partner", representative="QA Director", street_address="Testweg 2",
                postal_code="10115", city="Berlin", country="DE", contact_email="public@example.test",
                contact_phone="+49 (30) 123-456", vat_id="DE123456789", register_court="QA Amtsgericht",
                register_number="HRB 123")
    data.update(changes)
    return data


@pytest.mark.parametrize("lang", ["de", "ru"])
def test_staff_save_is_used_by_public_pages_and_download(client, django_user_model, lang):
    user = django_user_model.objects.create_superuser(username="public-owner", password="test-only")
    client.force_login(user)
    with override(lang):
        url = reverse("staff:workspace_preview", kwargs={"section": "store_settings"})
        token = client.get(url).context["form"]["state"].value()
        assert client.post(url, {**values(), "state": token}).status_code == 302
        public = Client()
        for name in ("shop:home", "support:help", "support:help_mobile", "support:impressum",
                     "support:datenschutz", "support:agb", "support:widerruf", "catalog:empty", "catalog:search_empty"):
            response = public.get(reverse(name))
            assert response.status_code == 200
            html = rendered_body(response)
            assert "QA Shop &amp; Partner" in html
            assert 'href="tel:+4930123456"' in html
            assert 'href="mailto:public@example.test"' in html
            assert "+49 (0) 89 215 489 0" not in html
            assert "service@maennermasche.de" not in html
        for slug in ("impressum", "datenschutz", "agb", "widerruf"):
            text = public.get(reverse("support:legal_download", kwargs={"slug": slug})).content.decode()
            html = rendered_body(public.get(reverse("support:" + slug)))
            assert values()["legal_name"] in text
            assert values()["street_address"] in text
            for placeholder in ("[vollständiger Name / Firma]", "[ladungsfähige Anschrift]",
                                "[Firma / Name und Anschrift]", "[Name / Firma]",
                                "[Name / Firma, Postanschrift und E-Mail des Unternehmers]"):
                assert placeholder not in text
                assert placeholder not in html
            assert "ENTWURF" in text or "ЧЕРНОВИК" in text


def test_empty_public_context_does_not_create_settings_or_invent_contacts():
    request = RequestFactory().get("/")
    request.user = AnonymousUser()
    with CaptureQueriesContext(connection) as queries:
        context = store_identity(request)
        assert store_identity(request) == context
        html = render_to_string("includes/footer.html", context, request=request)
    identity_reads = [query for query in queries if "shop_storeidentity" in query["sql"]]
    assert len(identity_reads) == 1
    assert all(query["sql"].lstrip().upper().startswith("SELECT") for query in queries)
    assert not StoreIdentity.objects.exists()
    assert "mailto:" not in html
    assert "tel:" not in html
    assert "service@maennermasche.de" not in html
    assert "800 6236637" not in html
    assert set(context["shop_identity"]) == set(PUBLIC_FIELDS) | {"phone_href", "email_href"}


def test_public_values_are_escaped_and_internal_revision_never_exposed():
    StoreIdentity.objects.create(**values(legal_name='<script>alert("identity")</script>',
                                         contact_phone="javascript:alert(1)"), revision=987654321)
    response = Client().get(reverse("support:impressum"))
    html = rendered_body(response)
    assert '&lt;script&gt;alert(&quot;identity&quot;)&lt;/script&gt;' in html
    assert '<script>alert("identity")</script>' not in html
    assert "javascript:alert(1)" not in html
    assert "987654321" not in html
    assert "revision" not in response.context["shop_identity"]


def test_public_page_reuses_one_read_for_all_contact_blocks_and_never_writes():
    StoreIdentity.objects.create(**values())
    client = Client()
    for route in ("support:help", "support:impressum"):
        with CaptureQueriesContext(connection) as queries:
            assert client.get(reverse(route)).status_code == 200
        assert len([q for q in queries if "shop_storeidentity" in q["sql"]]) == 1
        assert not any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries)
    StoreIdentity.objects.filter(pk=1).update(contact_email="updated@example.test")
    html = client.get(reverse("support:help")).content.decode()
    assert 'href="mailto:updated@example.test"' in html
    assert "public@example.test" not in html


def test_unused_identity_context_is_lazy_and_does_not_access_database(django_db_blocker, monkeypatch):
    def unexpected_read(request):
        raise AssertionError("A template without shop_identity must not read seller settings")

    monkeypatch.setattr("web.shop.context_processors.get_store_identity", unexpected_read)
    request = RequestFactory().get("/")
    with django_db_blocker.block():
        context = store_identity(request)
        assert Template("Email content without seller settings").render(Context(context)) == (
            "Email content without seller settings"
        )
    assert not hasattr(request, "_shop_public_identity")


@pytest.mark.parametrize("route", ["support:help", "support:help_mobile"])
def test_help_seller_blocks_use_saved_identity_without_claiming_shipping_sender(route):
    StoreIdentity.objects.create(**values())
    html = rendered_body(Client().get(reverse(route)))
    # Inspect the help body, excluding the shared footer which also shows identity.
    main = html.split("<main", 1)[1].split("</main>", 1)[0]
    assert "QA Shop &amp; Partner" in main
    assert "Testweg 2" in main
    assert "10115 Berlin" in main
    assert "[Betreiber noch zu bestätigen]" not in main
    assert "[Anschrift noch zu bestätigen]" not in main
    if route == "support:help":
        assert '<strong data-store-seller>QA Shop &amp; Partner</strong>' in main
        # Shipment label sender is a separate, unimplemented configuration.
        assert "<strong>[noch zu bestätigen]</strong>" in main


def test_help_seller_empty_state_has_no_fabricated_operator_or_address():
    html = rendered_body(Client().get(reverse("support:help")))
    assert "[Betreiber noch zu bestätigen]" not in html
    assert "[Anschrift noch zu bestätigen]" not in html
    assert "QA Shop" not in html
    assert "Testweg" not in html
    assert not StoreIdentity.objects.exists()
