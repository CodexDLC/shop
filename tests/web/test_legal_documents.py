from dataclasses import replace

import pytest
from django.test import Client
from django.urls import reverse
from django.utils.translation import override

from web.localization.translation import source_messages
from web.support.legal_documents import legal_documents

pytestmark = pytest.mark.django_db


@pytest.mark.django_db
@pytest.mark.parametrize("document", legal_documents(), ids=lambda item: item.slug)
def test_public_documents_read_without_database_mutation(document, django_assert_num_queries):
    client = Client(enforce_csrf_checks=True)
    with django_assert_num_queries(1):
        response = client.get(reverse(f"support:{document.url_name}"))
    assert response.status_code == 200
    assert not response.wsgi_request.user.is_authenticated
    assert "sessionid" not in response.cookies
    html = response.content.decode()
    assert 'id="legal-reader"' in html
    assert "ENTWURF" in html
    assert "[legal." not in html
    for section in document.sections:
        assert f'href="#{section.slug}"' in html
        assert f'id="{section.slug}"' in html
    for other in legal_documents():
        assert reverse(f"support:{other.url_name}") in html
    assert 'href="#"' not in html.split('<main class="legal-main', 1)[1].split("</main>", 1)[0]
    assert "window.print()" not in html  # Bound in a local script rather than a demo action.
    assert "legal-reader.js" in html


@pytest.mark.django_db
@pytest.mark.parametrize("document", legal_documents(), ids=lambda item: item.slug)
def test_download_contains_selected_complete_document(document, django_assert_num_queries):
    url = reverse("support:legal_download", kwargs={"slug": document.slug})
    with django_assert_num_queries(0):
        response = Client().get(url)
    assert response.status_code == 200
    assert response["Content-Type"] == "text/plain; charset=utf-8"
    assert response["Content-Disposition"] == (
        f'attachment; filename="{document.slug}-{document.version}.txt"'
    )
    assert response["X-Content-Type-Options"] == "nosniff"
    text = response.content.decode()
    assert "ENTWURF" in text
    assert "<html" not in text
    messages = source_messages()
    for section in document.sections:
        assert messages[section.title_key] in text
        for key in section.paragraph_keys + section.form_keys:
            assert messages[key] in text


def test_aliases_use_same_responsive_reader():
    for name in ("legal", "legal_mobile", "datenschutz"):
        response = Client().get(reverse(f"support:{name}"))
        assert response.status_code == 200
        assert response.context["legal_document"].slug == "datenschutz"
        assert 'data-real-legal="true"' in response.content.decode()


def test_unknown_documents_and_post_are_rejected():
    client = Client()
    assert client.get("/rechtliches/unbekannt/").status_code == 404
    assert client.get("/rechtliches/unbekannt/download/").status_code == 404
    assert client.post(reverse("support:impressum")).status_code == 405
    assert client.post(reverse("support:legal_download", kwargs={"slug": "agb"})).status_code == 405


def test_document_text_is_escaped_and_provider_markup_cannot_execute(monkeypatch):
    import web.localization.translation as translation
    import web.support.legal_document_view as view_module

    messages = {**source_messages(), "legal.test.escape": '<img src=x onerror="alert(1)">'}
    monkeypatch.setattr(translation, "gettext", lambda key: key)
    monkeypatch.setattr(translation, "source_messages", lambda: messages)
    document = legal_documents()[0]
    section = replace(document.sections[0], paragraph_keys=("legal.test.escape",))
    monkeypatch.setattr(view_module, "get_legal_document", lambda slug: replace(
        document, sections=(section,)
    ))
    html = Client().get(reverse("support:datenschutz")).content.decode()
    assert '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;' in html
    assert '<img src=x onerror="alert(1)">' not in html


def test_all_structured_content_keys_exist():
    messages = source_messages()
    for document in legal_documents():
        keys = [document.title_key, document.summary_key]
        for section in document.sections:
            keys.extend((section.title_key, *section.paragraph_keys, *section.form_keys))
            for pair in section.cards:
                keys.extend(pair)
            for row in section.rows:
                keys.extend(row)
        assert not set(keys).difference(messages)


def test_localized_routes_keep_german_fallback():
    with override("ru"):
        url = reverse("support:impressum")
        assert url == "/ru/rechtliches/impressum/"
        response = Client().get(url)
    assert response.status_code == 200
    assert "Impressum" in response.content.decode()
