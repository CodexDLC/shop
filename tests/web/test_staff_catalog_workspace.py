import pytest
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from web.catalog.models import Brand, Product, ProductReview, SizeGuide
from web.staff.catalog_workspace.forms import guide_rows, reference_form
from web.staff.catalog_workspace.selectors import resource_queryset
from web.staff.models import StaffAuditEvent

pytestmark = pytest.mark.django_db


@pytest.fixture
def catalog_editor(django_user_model):
    user = django_user_model.objects.create_user(username="workspace-catalog-editor", is_staff=True)
    user.user_permissions.add(*Permission.objects.filter(content_type__app_label="catalog"))
    return user


def test_resource_endpoints_require_staff_and_permission(client, django_user_model):
    user = django_user_model.objects.create_user(username="catalog-no-permissions", is_staff=True)
    client.force_login(user)
    for name in ("brands", "categories", "materials", "properties", "tags", "size_guides", "reviews", "photos"):
        assert client.get(reverse(f"staff:{name}")).status_code == 403
    user.is_staff = False
    user.user_permissions.add(*Permission.objects.filter(content_type__app_label="catalog"))
    user.save()
    assert client.get(reverse("staff:brands")).status_code == 403


def test_real_lists_details_search_and_pagination(client, catalog_editor):
    call_command("seed_demo_catalog")
    client.force_login(catalog_editor)
    for name in ("brands", "categories", "materials", "properties", "tags", "size_guides", "reviews", "photos"):
        assert client.get(reverse(f"staff:{name}")).status_code == 200
    brand = Brand.objects.first()
    response = client.get(reverse("staff:brand_detail", kwargs={"pk": brand.pk}))
    assert response.status_code == 200
    assert brand.name.encode() in response.content
    Brand.objects.bulk_create([Brand(name=f"Searchable {index}", slug=f"search-{index}") for index in range(35)])
    response = client.get(reverse("staff:brands"), {"q": "Searchable", "page": "2"})
    assert response.context["page_obj"].paginator.count == 35
    assert len(response.context["rows"]) == 5


def test_reference_save_validation_audit_and_stale(client, catalog_editor):
    client.force_login(catalog_editor)
    response = client.post(reverse("staff:brand_add"), {"name": "Real brand", "slug": "real-brand"})
    assert response.status_code == 302
    brand = Brand.objects.get(slug="real-brand")
    url = reverse("staff:brand_edit", kwargs={"pk": brand.pk})
    state = client.get(url).context["original_state"]
    assert client.post(url, {"name": "Changed", "slug": brand.slug, "original_state": state}).status_code == 302
    assert StaffAuditEvent.objects.filter(action="reference.brand.saved").count() == 2
    assert client.post(url, {"name": "Stale", "slug": brand.slug, "original_state": state}).status_code == 400
    brand.refresh_from_db()
    assert brand.name == "Changed"
    assert client.post(reverse("staff:brand_add"), {"name": "Duplicate", "slug": brand.slug}).status_code == 400


def test_published_reference_cannot_bypass_workflow(client, catalog_editor):
    call_command("seed_demo_catalog")
    client.force_login(catalog_editor)
    product = Product.objects.filter(is_active=True).first()
    url = reverse("staff:brand_edit", kwargs={"pk": product.brand_id})
    state = client.get(url).context["original_state"]
    assert client.post(url, {"name": "Changed published brand", "slug": product.brand.slug,
                             "original_state": state}).status_code == 400
    product.brand.refresh_from_db()
    assert product.brand.name != "Changed published brand"
    assert not StaffAuditEvent.objects.exists()


def test_reference_csrf(catalog_editor):
    client = Client(enforce_csrf_checks=True)
    client.force_login(catalog_editor)
    assert client.post(reverse("staff:brand_add"), {"name": "Unsafe", "slug": "unsafe"}).status_code == 403
    assert not Brand.objects.filter(slug="unsafe").exists()


def test_guide_publication_and_measurements_validation():
    brand = Brand.objects.create(name="Guide brand", slug="guide-brand")
    data = {"brand": brand.pk, "title": "Guide", "is_published": "on"}
    assert not reference_form("size_guides", data).is_valid()
    form = reference_form("size_guides", {"brand": brand.pk, "title": "Guide"})
    assert form.is_valid()
    guide = form.save()
    assert not guide.is_published
    rows = guide_rows({"rows-TOTAL_FORMS": "1", "rows-INITIAL_FORMS": "0", "rows-0-size": "M",
                       "rows-0-position": "0", "rows-0-waist_min_cm": "90", "rows-0-waist_max_cm": "80"}, guide)
    assert not rows.is_valid()


def test_guide_and_rows_save_atomically(client, catalog_editor):
    brand = Brand.objects.create(name="Guide brand", slug="guide-brand")
    client.force_login(catalog_editor)
    data = {"brand": brand.pk, "title": "Measured guide", "rows-TOTAL_FORMS": "1", "rows-INITIAL_FORMS": "0",
            "rows-0-size": "M", "rows-0-position": "0", "rows-0-waist_min_cm": "80", "rows-0-waist_max_cm": "90"}
    assert client.post(reverse("staff:size_guide_add"), data).status_code == 302
    guide = SizeGuide.objects.get(title="Measured guide")
    assert guide.rows.get().size == "M"
    assert not guide.is_published
    assert client.get(reverse("staff:size_guide_edit", kwargs={"pk": guide.pk})).status_code == 200


def test_guide_binding_is_preserved_and_bad_rows_do_not_create_guide(client, catalog_editor):
    brand = Brand.objects.create(name="Original", slug="original-guide-brand")
    other = Brand.objects.create(name="Other", slug="other-guide-brand")
    guide = SizeGuide.objects.create(brand=brand, title="Bound guide")
    form = reference_form("size_guides", {"brand": other.pk, "title": "Changed"}, guide)
    assert form.is_valid()
    assert form.save().brand_id == brand.pk
    client.force_login(catalog_editor)
    data = {"brand": other.pk, "title": "Invalid guide", "rows-TOTAL_FORMS": "1", "rows-INITIAL_FORMS": "0",
            "rows-0-size": "M", "rows-0-position": "0", "rows-0-waist_min_cm": "90", "rows-0-waist_max_cm": "80"}
    assert client.post(reverse("staff:size_guide_add"), data).status_code == 400
    assert not SizeGuide.objects.filter(title="Invalid guide").exists()


def test_guide_row_mutation_requires_separate_model_permission(client, django_user_model):
    brand = Brand.objects.create(name="Guide", slug="row-permission-brand")
    user = django_user_model.objects.create_user(username="guide-no-row", is_staff=True)
    user.user_permissions.add(Permission.objects.get(content_type__app_label="catalog", codename="add_sizeguide"))
    client.force_login(user)
    data = {"brand": brand.pk, "title": "Not allowed", "rows-TOTAL_FORMS": "1", "rows-INITIAL_FORMS": "0",
            "rows-0-size": "M", "rows-0-position": "0", "rows-0-waist_min_cm": "80", "rows-0-waist_max_cm": "90"}
    assert client.post(reverse("staff:size_guide_add"), data).status_code == 403
    assert not SizeGuide.objects.exists()


def test_reviews_readonly_and_selector_query_count_constant(client, catalog_editor):
    call_command("seed_demo_catalog")
    product = Product.objects.first()
    review = ProductReview.objects.create(product=product, rating=4, body="Real review", status="pending")
    client.force_login(catalog_editor)
    response = client.get(reverse("staff:review_detail", kwargs={"pk": review.pk}))
    assert response.status_code == 200
    assert b"Real review" in response.content
    assert client.post(reverse("staff:review_detail", kwargs={"pk": review.pk}), {"status": "approved"}).status_code == 405
    for count in (1, 10):
        with CaptureQueriesContext(connection) as queries:
            for image in resource_queryset("photos")[:count]:
                str(image.product.brand.name)
        assert len(queries) == 1
