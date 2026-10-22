import json

import pytest
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse
from django.utils.translation import override

from web.catalog.models import Brand, Category, Product, ProductInformation, ProductVariant
from web.seo.models import SeoPage, SeoRule
from web.seo.workspace import get_page, publish_page, save_draft
from web.staff.seo_workspace.selectors import page_schema

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def german():
    with override("de"):
        yield


@pytest.fixture
def product():
    brand = Brand.objects.create(slug="seo-brand", name="SEO Brand")
    category = Category.objects.create(slug="seo-category", name_key="seo-category", name_de="SEO Kategorie")
    return Product.objects.create(slug="seo-product", model_name="SEO Produkt", brand=brand, category=category)


@pytest.fixture
def actor(client, django_user_model):
    def make(*permissions, staff=True):
        account = django_user_model.objects.create_user(username=f"seo-{len(permissions)}-{staff}", is_staff=staff)
        account.user_permissions.add(*Permission.objects.filter(content_type__app_label="seo", codename__in=permissions))
        client.force_login(account)
        return account
    return make


def page_url(product, language="de"):
    return reverse("staff:seo_page", kwargs={"kind": "product", "key": product.slug}) + "?content_language=" + language


def values(version=0, **kwargs):
    return {"version": version, "action": "save", **kwargs}


@pytest.mark.parametrize("name", ["seo_overview", "seo_pages", "seo_rules", "seo_indexing"])
def test_view_permission_alone_reads_workspace_without_catalog_permission(client, actor, name):
    account = actor("view_seopage")
    assert not account.has_perm("catalog.view_product")
    response = client.get(reverse("staff:" + name))
    assert response.status_code == 200
    assert "[staff.seo." not in response.content.decode()
    assert not SeoPage.objects.exists()
    assert not SeoRule.objects.exists()


@pytest.mark.parametrize("permissions,staff", [((), True), (("view_seopage",), False), (("change_metadata",), True)])
def test_seo_entry_requires_staff_and_view_permission(client, actor, permissions, staff):
    actor(*permissions, staff=staff)
    assert client.get(reverse("staff:seo_overview")).status_code == 403


def test_catalog_rights_do_not_grant_seo_access(client, django_user_model):
    account = django_user_model.objects.create_user(username="catalog-only-seo", is_staff=True)
    account.user_permissions.add(*Permission.objects.filter(content_type__app_label="catalog"))
    client.force_login(account)
    assert client.get(reverse("staff:seo_pages")).status_code == 403


def test_metadata_editor_draft_publish_reset_and_restore(client, actor, product):
    actor("view_seopage", "change_metadata", "publish_seo")
    url = page_url(product)
    response = client.get(url)
    assert "body" not in response.context["form"].fields
    assert 'value="reset:title"' not in response.content.decode()
    assert client.post(url, values(title="Eigener Titel", description="Eigene Beschreibung")).status_code == 302
    assert SeoPage.objects.get().published == {}
    response = client.get(url)
    assert response.context["preview"]["title"].startswith("Eigener Titel")
    assert 'value="reset:title"' in response.content.decode()
    assert client.post(url, values(1, action="publish", title="Eigener Titel", description="Eigene Beschreibung")).status_code == 302
    assert get_page("product", product.slug)["effective"]["title"].startswith("Eigener Titel")
    assert client.post(url, values(2, action="reset:title")).status_code == 302
    assert SeoPage.objects.get().published["title"] == "Eigener Titel"
    assert client.post(url, values(3, action="publish", title="", description="Eigene Beschreibung")).status_code == 302
    assert not SeoPage.objects.get().published["title"]
    assert client.post(url, values(4, action="restore")).status_code == 302
    assert SeoPage.objects.get().published["title"] == "Eigener Titel"


def test_metadata_editor_cannot_mutate_body_or_catalog_facts(client, actor, product):
    actor("view_seopage", "change_metadata")
    assert client.post(page_url(product), values(body="forbidden")).status_code == 403
    assert client.post(page_url(product), values(title="Allowed", model_name="Hacked", is_active="")).status_code == 302
    product.refresh_from_db()
    assert product.model_name == "SEO Produkt"
    assert product.is_active
    assert "body" not in SeoPage.objects.get().draft


def test_text_editor_has_no_metadata_fields_and_cannot_publish(client, actor, product):
    actor("view_seopage", "change_text")
    response = client.get(page_url(product))
    assert set(response.context["form"].fields) == {"version", "body"}
    assert client.post(page_url(product), values(title="forbidden")).status_code == 403
    assert client.post(page_url(product), values(body="New text")).status_code == 302
    assert client.post(page_url(product), values(1, action="publish", body="New text")).status_code == 403


def test_stale_submission_preserves_input_and_stored_draft(client, actor, product):
    actor("view_seopage", "change_metadata")
    assert client.post(page_url(product), values(title="First")).status_code == 302
    response = client.post(page_url(product), values(title="Second"))
    assert response.status_code == 409
    assert response.context["form"]["title"].value() == "Second"
    assert SeoPage.objects.get().draft["title"] == "First"
    assert "SEO draft changed" not in response.content.decode()


def test_publish_rejects_unsaved_edits(client, actor, product):
    actor("view_seopage", "change_metadata", "publish_seo")
    client.post(page_url(product), values(title="Saved"))
    assert client.post(page_url(product), values(1, action="publish", title="Unsaved")).status_code == 409
    assert not SeoPage.objects.get().published


def test_publish_only_user_sees_draft_but_cannot_publish_another_editors_fields(client, actor, product):
    SeoPage.objects.create(kind="product", key=product.slug, language="de", version=1,
                           draft={"title": "Awaiting metadata editor"})
    actor("view_seopage", "publish_seo")
    response = client.get(page_url(product))
    assert not response.context["can_publish"]
    assert 'value="publish"' not in response.content.decode()
    assert client.post(page_url(product), values(1, action="publish")).status_code == 403


def test_first_published_override_can_restore_original_automatic_version(client, actor, product):
    actor("view_seopage", "change_metadata", "publish_seo")
    url = page_url(product)
    client.post(url, values(title="Override"))
    client.post(url, values(1, action="publish", title="Override"))
    assert SeoPage.objects.get().previous == {}
    response = client.get(url)
    assert response.context["can_restore"]
    assert 'value="restore"' in response.content.decode()
    assert client.post(url, values(2, action="restore")).status_code == 302
    assert SeoPage.objects.get().published == {}


def test_plain_text_preview_escapes_payload_and_current_diff_visible(client, actor, product):
    account = actor("view_seopage", "change_text")
    payload = '<script>alert("seo")</script>'
    save_draft(account, "product", product.slug, "de", expected_version=0, values={"body": payload})
    response = client.get(page_url(product))
    html = response.content.decode()
    assert payload not in html
    assert "&lt;script&gt;" in html
    assert response.context["seo_page"]["effective"]["body"] != payload
    assert response.context["preview"]["body"] == payload


@pytest.mark.parametrize("language", ["de", "ru"])
def test_interface_and_content_language_are_independent(client, actor, product, language):
    actor("view_seopage", "change_metadata")
    with override(language):
        response = client.get(page_url(product, "ru"))
        assert response.status_code == 200
        assert response.context["content_language"] == "ru"
        assert response.context["LANGUAGE_CODE"] == language
        assert "[staff.seo." not in response.content.decode()
        assert client.post(page_url(product, "ru"), values(title="RU content")).status_code == 302
    assert SeoPage.objects.get().language == "ru"


def test_search_name_sku_url_and_static_with_bounded_pages(client, actor, product):
    actor("view_seopage")
    ProductVariant.objects.create(product=product, sku="SEO-SKU-490", size="M", color_code="blue", price="10.00")
    for query in ("SEO Produkt", "SEO-SKU-490", reverse("catalog:detail", kwargs={"slug": product.slug})):
        response = client.get(reverse("staff:seo_pages"), {"q": query})
        assert any(row["key"] == product.slug for row in response.context["page_obj"])
        assert len(response.context["page_obj"]) <= 20
    response = client.get(reverse("staff:seo_pages"), {"q": reverse("shop:home")})
    assert any(row["key"] == "shop:home" for row in response.context["page_obj"])


def test_legal_body_is_not_editable(client, actor):
    actor("view_seopage", "change_text", "change_metadata")
    url = reverse("staff:seo_page", kwargs={"kind": "static", "key": "support:impressum"})
    response = client.get(url)
    assert "body" not in response.context["form"].fields
    assert client.post(url, values(body="overwrite legal facts")).status_code == 403


def test_rule_save_preview_publish_requires_exact_saved_preview(client, actor, product):
    actor("view_seopage", "manage_rules", "publish_seo")
    url = reverse("staff:seo_rules")
    data = values(title_template="{brand} {name}", description_template="{name} bei {site}")
    assert client.post(url, data).status_code == 302
    response = client.get(url)
    assert response.context["rule_examples"][0]["label"] == product.model_name
    token = response.context["rule_preview_state"]
    assert client.post(url, {**data, "version": 1, "action": "publish"}).status_code == 409
    assert client.post(url, {**data, "version": 1, "action": "publish", "preview_state": token}).status_code == 302
    assert SeoRule.objects.get().published["title_template"] == "{brand} {name}"


def test_rule_edit_requires_manage_permission_and_validation_localized(client, actor, product):
    actor("view_seopage", "change_metadata")
    assert client.post(reverse("staff:seo_rules"), values(title_template="{name}")).status_code == 403


def test_invalid_rule_does_not_publish_or_expose_backend_english(client, actor, product):
    actor("view_seopage", "manage_rules")
    response = client.post(reverse("staff:seo_rules"), values(title_template="{name.__class__}"))
    assert response.status_code == 400
    assert not SeoRule.objects.exists()
    assert "Unsupported" not in response.content.decode()


def test_indexing_readonly_and_get_mutations_rejected(client, actor):
    actor("view_seopage")
    url = reverse("staff:seo_indexing")
    assert 'type="submit"' not in client.get(url).content.decode().split('<section class="seo-workspace"')[1]
    assert client.post(url, {"SEO_INDEXING_ENABLED": "true"}).status_code == 405


def test_overview_counts_and_checks_are_real(client, actor, product):
    account = actor("view_seopage", "change_metadata")
    save_draft(account, "product", product.slug, "de", expected_version=0, values={"title": "X" * 120})
    response = client.get(reverse("staff:seo_overview"))
    assert response.context["summary"]["drafts"] == 1
    assert response.context["summary"]["published"] == 0
    assert response.context["recent_pages"][0]["key"] == product.slug
    assert "long_title" in response.context["recent_pages"][0]["checks"]


def test_product_jsonld_is_actual_readonly_and_does_not_invent_offers(client, actor, product, settings):
    actor("view_seopage")
    settings.SEO_PUBLIC_ORIGIN = "https://example.com"
    response = client.get(page_url(product))
    schema = json.loads(response.context["technical_schema"])
    assert schema["@graph"][0]["name"] == "SEO Brand SEO Produkt"
    assert "offers" not in schema["@graph"][0]
    assert "aggregateRating" not in schema["@graph"][0]
    assert 'name="schema"' not in response.content.decode()


@pytest.mark.parametrize("language", ["de", "ru"])
def test_technical_jsonld_matches_public_literal_seo_text(client, actor, product, settings, language):
    settings.SEO_PUBLIC_ORIGIN = "https://example.com"
    account = actor("view_seopage", "change_text", "publish_seo")
    body = 'Editorial <strong>literal text</strong> & </script><script>alert("seo")</script>'
    row = save_draft(account, "product", product.slug, language, expected_version=0, values={"body": body})
    publish_page(account, "product", product.slug, language, expected_version=row.version)
    with override(language):
        path = reverse("catalog:detail", kwargs={"slug": product.slug})
        public_response = client.get(path)
    technical = page_schema(get_page("product", product.slug, language), language)
    public = public_response.context["seo"]["schema"]
    assert json.loads(technical) == json.loads(public)
    assert json.loads(technical)["@graph"][0]["description"] == body
    assert "</script>" not in technical
    response = client.get(page_url(product, language))
    assert body not in response.content.decode()
    assert "&lt;strong&gt;" in response.content.decode()


@pytest.mark.parametrize("language", ["de", "ru"])
def test_technical_jsonld_uses_public_version_before_publish_and_after_reset(client, actor, product,
                                                                          settings, language):
    settings.SEO_PUBLIC_ORIGIN = "https://example.com"
    account = actor("view_seopage", "change_text", "publish_seo")
    ProductInformation.objects.create(product=product, language_code="de", description="Original <b>Beschreibung</b>")

    def compare_public():
        with override(language):
            response = client.get(reverse("catalog:detail", kwargs={"slug": product.slug}))
        technical = page_schema(get_page("product", product.slug, language), language)
        assert json.loads(technical) == json.loads(response.context["seo"]["schema"])

    compare_public()
    row = save_draft(account, "product", product.slug, language, expected_version=0,
                     values={"body": "Unpublished <strong>literal text</strong>"})
    compare_public()
    row = publish_page(account, "product", product.slug, language, expected_version=row.version)
    compare_public()
    row = save_draft(account, "product", product.slug, language, expected_version=row.version, values={"body": ""})
    compare_public()
    publish_page(account, "product", product.slug, language, expected_version=row.version)
    compare_public()


def test_csrf_enforced(django_user_model, product):
    account = django_user_model.objects.create_superuser(username="seo-csrf", password="test-only")
    client = Client(enforce_csrf_checks=True)
    client.force_login(account)
    client.get(page_url(product))
    assert client.post(page_url(product), values(title="Blocked")).status_code == 403
    assert not SeoPage.objects.exists()


@pytest.mark.parametrize("suffix", ["?content_language=fr", "?content_language=de&unused=x"])
def test_locale_validation(client, actor, product, suffix):
    actor("view_seopage")
    url = reverse("staff:seo_page", kwargs={"kind": "product", "key": product.slug})
    assert client.get(url + suffix).status_code == (404 if "fr" in suffix else 200)


def test_unknown_page_type_is_not_a_server_error(client, actor):
    actor("view_seopage")
    url = reverse("staff:seo_page", kwargs={"kind": "unknown", "key": "unknown"})
    assert client.get(url).status_code == 404
