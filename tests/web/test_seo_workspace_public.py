import json
import re

import pytest
from django.contrib.auth.models import Permission, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import Client, RequestFactory, override_settings
from django.urls import resolve

from web.catalog.models import Product
from web.seo.models import SeoAudit, SeoPage, SeoRule
from web.seo.public import apply_public_overlay
from web.seo.workspace import (
    get_page,
    get_rule,
    preview_rule,
    publish_page,
    publish_rule,
    restore_previous,
    save_draft,
    save_rule_draft,
    search_pages,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def product():
    call_command("seed_demo_catalog")
    return Product.objects.get(slug="manstore-m2223")


@pytest.fixture
def editor():
    return User.objects.create_superuser("seo", "seo@example.test", "test")


def scoped(*codenames):
    user = User.objects.create_user("scoped-" + str(User.objects.count()))
    user.user_permissions.add(*Permission.objects.filter(content_type__app_label="seo", codename__in=codenames))
    return user


def publish(editor, kind, key, values, language="de"):
    state = get_page(kind, key, language)
    row = save_draft(editor, kind, key, language, expected_version=state["version"], values=values)
    return publish_page(editor, kind, key, language, expected_version=row.version)


@override_settings(SEO_PUBLIC_ORIGIN="https://store.example.com", SEO_INDEXING_ENABLED=True)
def test_draft_publish_visible_plain_text_and_schema_agree_without_catalog_changes(product, editor):
    key = product.slug
    original = product.model_name
    payload = "Editorial <script>alert('x')</script>\nSecond line"
    row = save_draft(editor, "product", key, "de", expected_version=0,
                     values={"title": "My metadata", "body": payload})
    assert "My metadata" not in Client().get(f"/produkt/{key}/").content.decode()
    publish_page(editor, "product", key, "de", expected_version=row.version)
    response = Client().get(f"/produkt/{key}/")
    html = response.content.decode()
    assert "<title>My metadata |" in html
    assert "&lt;script&gt;alert" in html
    assert "<script>alert" not in html
    schema = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
    item = next(item for item in schema["@graph"] if item["@type"] == "Product")
    assert item["description"] == payload
    assert "offers" not in item
    assert "noindex" in response["X-Robots-Tag"]
    product.refresh_from_db()
    assert product.model_name == original
    preview = get_page("product", key)
    assert preview["effective"]["title"] in html
    assert not preview["has_draft"]


def test_versions_restore_and_per_field_auto_are_explicit(product, editor):
    first = publish(editor, "product", product.slug, {"title": "First", "body": "First text"})
    second = publish(editor, "product", product.slug, {"title": "Second"})
    with pytest.raises(ValidationError, match="changed"):
        save_draft(editor, "product", product.slug, "de", expected_version=first.version, values={"title": "Lost"})
    restored = restore_previous(editor, "product", product.slug, "de", expected_version=second.version)
    assert restored.published["title"] == "First"
    reset = save_draft(editor, "product", product.slug, "de", expected_version=restored.version, values={"title": ""})
    assert get_page("product", product.slug)["effective"]["title"].startswith("First")
    publish_page(editor, "product", product.slug, "de", expected_version=reset.version)
    assert get_page("product", product.slug)["effective"]["title"].startswith("MANSTORE M2223")
    assert SeoAudit.objects.count() == 7
    assert set(SeoAudit.objects.values_list("action", flat=True)) == {"save", "publish", "restore"}
    assert "First text" not in str(list(SeoAudit.objects.values()))


def test_publish_permission_cannot_publish_someone_elses_unauthorized_text_draft(product, editor):
    row = save_draft(editor, "product", product.slug, "de", expected_version=0,
                     values={"title": "Metadata", "body": "Protected text"})
    metadata_publisher = scoped("view_seopage", "change_metadata", "publish_seo")
    with pytest.raises(PermissionDenied):
        publish_page(metadata_publisher, "product", product.slug, "de", expected_version=row.version)
    with pytest.raises(PermissionDenied):
        save_draft(metadata_publisher, "product", product.slug, "de", expected_version=row.version, values={"body": ""})
    assert not SeoPage.objects.get(pk=row.pk).published


@pytest.mark.parametrize("permissions,allowed", [
    ([], False), (["view_seopage"], False), (["change_metadata"], False),
    (["view_seopage", "change_text"], False), (["view_seopage", "change_metadata"], True),
])
def test_draft_metadata_requires_own_view_and_field_permission(product, permissions, allowed):
    user = scoped(*permissions)
    if allowed:
        save_draft(user, "product", product.slug, "de", expected_version=0, values={"title": "Allowed"})
    else:
        with pytest.raises(PermissionDenied):
            save_draft(user, "product", product.slug, "de", expected_version=0, values={"title": "Denied"})


@override_settings(SEO_PUBLIC_ORIGIN="https://store.example.com", SEO_INDEXING_ENABLED=True)
def test_overlay_language_is_separate_and_ru_never_opens_indexing(product, editor):
    publish(editor, "product", product.slug, {"title": "German only"})
    assert "German only" not in Client().get(f"/ru/produkt/{product.slug}/").content.decode()
    publish(editor, "product", product.slug, {"title": "Русское название", "body": "Русский текст"}, language="ru")
    ru = Client().get(f"/ru/produkt/{product.slug}/")
    assert "Русское название" in ru.content.decode()
    assert "noindex" in ru["X-Robots-Tag"]
    assert "hreflang=" not in ru.content.decode()


@override_settings(SEO_PUBLIC_ORIGIN="https://store.example.com", SEO_INDEXING_ENABLED=True)
def test_category_legacy_metadata_fallback_and_brand_static_body_overlays(product, editor):
    category = product.category
    category.seo_title = "Legacy category title"
    category.seo_description = "Legacy category description"
    category.save()
    path = f"/katalog/?category={category.slug}"
    assert "Legacy category title" in Client().get(path).content.decode()
    publish(editor, "category", category.slug, {"title": "Category overlay", "body": "Category visible intro"})
    response = Client().get(path)
    assert "Category overlay" in response.content.decode()
    assert "Category visible intro" in response.content.decode()
    assert "noindex" in response["X-Robots-Tag"]
    category.refresh_from_db()
    assert category.seo_title == "Legacy category title"
    publish(editor, "brand", product.brand.slug, {"title": "Brand title", "body": "Brand intro"})
    assert "Brand intro" in Client().get(f"/katalog/?brand={product.brand.slug}").content.decode()
    publish(editor, "static", "shop:home", {"body": "Home intro"})
    assert "Home intro" in Client().get("/").content.decode()
    with pytest.raises(ValidationError):
        save_draft(editor, "static", "support:impressum", "de", expected_version=0, values={"body": "Fake legal data"})


def test_safe_rule_drafts_validation_actual_preview_and_publication(product, editor):
    for bad in ("{name.__class__}", "{{ name }}", "{name!r}", "{name:80}", "<b>{name}</b>", "{unknown}"):
        with pytest.raises(ValidationError):
            save_rule_draft(editor, "product", "de", expected_version=0, values={"title_template": bad})
    values = {"title_template": "{brand} {name} — {site}", "description_template": "{category}: {name}"}
    examples = preview_rule("product", "de", values)
    assert examples and len(examples) <= 3
    assert "{" not in examples[0]["title"]
    row = save_rule_draft(editor, "product", "de", expected_version=0, values=values)
    assert not get_rule("product")["published"]
    publish_rule(editor, "product", "de", expected_version=row.version)
    html = Client().get(f"/produkt/{product.slug}/").content.decode()
    title = re.search("<title>(.*?)</title>", html).group(1)
    assert title.count("Unterwäsche Atelier") <= 1
    assert "—" in title


def test_search_is_bounded_includes_static_and_matches_name_sku_url(product, django_assert_max_num_queries):
    with django_assert_max_num_queries(2):
        results = search_pages()
        assert len(results) <= 20
        assert any(row["kind"] == "static" for row in results)
    assert any(row["key"] == product.slug for row in search_pages(query=product.variants.first().sku))
    assert any(row["key"] == product.slug for row in search_pages(query=f"https://store.example.com/produkt/{product.slug}/"))
    assert any(row["key"] == "support:help" for row in search_pages(query="/service/"))


def test_public_lookup_is_request_memoized_and_private_routes_do_not_query(product, django_assert_num_queries):
    request = RequestFactory().get("/")
    request.resolver_match = resolve("/")
    request.LANGUAGE_CODE = "de"
    with django_assert_num_queries(2):
        apply_public_overlay(request, {})
        apply_public_overlay(request, {})
    request = RequestFactory().get("/accounts/login/")
    request.resolver_match = resolve(request.path)
    with django_assert_num_queries(0):
        apply_public_overlay(request, {})


def test_rules_write_requires_manage_and_publish_separately(editor):
    user = scoped("view_seopage", "manage_rules")
    row = save_rule_draft(user, "static", "de", expected_version=0, values={"title_template": "{name}"})
    with pytest.raises(PermissionDenied):
        publish_rule(user, "static", "de", expected_version=row.version)
    unauthorized = scoped("view_seopage", "publish_seo")
    with pytest.raises(PermissionDenied):
        publish_rule(unauthorized, "static", "de", expected_version=row.version)
    assert SeoRule.objects.count() == 1


def test_page_search_localizes_legacy_category_labels_without_extra_queries(product, django_assert_max_num_queries):
    with django_assert_max_num_queries(2):
        rows = list(search_pages(kind="category"))
    category = next(row for row in rows if row["key"] == product.category.slug)
    assert category["label"] == product.category.name


def test_audit_failure_rolls_back_mutation(product, editor, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("Simulated journal failure")

    monkeypatch.setattr("web.staff.audit.record_staff_action", fail)
    with pytest.raises(RuntimeError):
        save_draft(editor, "product", product.slug, "de", expected_version=0, values={"title": "Never persisted"})
    assert not SeoPage.objects.exists()
    assert not SeoAudit.objects.exists()


@pytest.mark.parametrize("query", ["https://[invalid/path", "https://[::1/path"])
def test_malformed_pasted_url_returns_empty_bounded_page(query, django_assert_num_queries):
    with django_assert_num_queries(0):
        results = search_pages(query=query)
        assert list(results) == []
        assert results.paginator.count == 0


def test_russian_seo_description_has_own_language_without_relabelling_german_facts(product, editor):
    from web.catalog.models import ProductInformation

    ProductInformation.objects.update_or_create(
        product=product, language_code="de", defaults={
            "description": "German source description", "composition": "German composition", "fit": "German fit",
        },
    )
    publish(editor, "product", product.slug, {"body": "Русское SEO описание"}, language="ru")
    response = Client().get(f"/ru/produkt/{product.slug}/")
    assert response.context["description_language"] == "ru"
    assert response.context["information_language"] == "de"
    assert response.context["product_information"]["composition"] == "German composition"
    assert response.context["product_information"]["fit"] == "German fit"
    html = response.content.decode()
    description = html.split('id="product-description"', 1)[1].split('data-information-facts', 1)[0]
    assert "Русское SEO описание" in description
    assert 'data-description-fallback' not in description
    assert 'data-facts-fallback' in html
