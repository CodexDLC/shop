import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_seo_only_staff_can_navigate_without_catalog_or_settings_rights(client, django_user_model):
    user = django_user_model.objects.create_user(username="seo-navigation", is_staff=True)
    user.user_permissions.add(Permission.objects.get(content_type__app_label="seo", codename="view_seopage"))
    client.force_login(user)
    response = client.get(reverse("staff:seo_overview"))
    assert response.status_code == 200
    assert [group["key"] for group in response.context["staff_primary_groups"]] == ["management"]
    rows = response.context["staff_sidebar_rows"]
    assert any(str(row["item"].url) == reverse("staff:seo_overview") for row in rows)
    assert all(str(row["item"].url) not in {reverse("staff:products"), reverse("staff:settings")} for row in rows)
    assert response.context["staff_global_settings_url"] is None
    assert client.get(reverse("staff:products")).status_code == 403
    assert client.get(reverse("staff:workspace_preview", kwargs={"section": "store_settings"})).status_code == 403


def test_catalog_access_does_not_grant_seo_access(client, django_user_model):
    user = django_user_model.objects.create_user(username="catalog-navigation", is_staff=True)
    user.user_permissions.add(Permission.objects.get(content_type__app_label="catalog", codename="view_product"))
    client.force_login(user)
    response = client.get(reverse("staff:products"))
    assert response.status_code == 200
    assert all(str(row["item"].url) != reverse("staff:seo_overview") for row in response.context["staff_sidebar_rows"])
    assert client.get(reverse("staff:seo_overview")).status_code == 403


def test_category_editor_preserves_legacy_seo_fields_even_with_forged_post(client, django_user_model):
    from web.catalog.models import Category

    category = Category.objects.create(slug="protected-seo", name_de="Kategorie", name_key="category.test",
                                       seo_title="Legacy title", seo_description="Legacy description")
    user = django_user_model.objects.create_user(username="category-seo-boundary", is_staff=True)
    user.user_permissions.add(*Permission.objects.filter(content_type__app_label="catalog",
                                                        codename__in=["view_category", "change_category"]))
    client.force_login(user)
    url = reverse("staff:category_edit", kwargs={"pk": category.pk})
    initial = client.get(url)
    assert "seo_title" not in initial.context["form"].fields
    assert "seo_description" not in initial.context["form"].fields
    response = client.post(url, {"name_de": category.name_de, "name_ru": "", "slug": category.slug,
                                "parent": "", "section": category.section, "position": 0, "is_visible": "on",
                                "original_state": initial.context["original_state"],
                                "seo_title": "Forged title", "seo_description": "Forged description"})
    assert response.status_code == 302
    category.refresh_from_db()
    assert category.seo_title == "Legacy title"
    assert category.seo_description == "Legacy description"
