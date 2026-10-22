import pytest
from django.core.management import call_command
from django.urls import reverse

from web.catalog.models import Product, ProductImage, ProductVariant

pytestmark = pytest.mark.django_db


def test_home_uses_database_instead_of_presentation_mock(client, django_assert_num_queries):
    call_command("seed_demo_catalog")
    Product.objects.filter(slug="manstore-m2223").update(model_name="Database Model")
    with django_assert_num_queries(5):
        response = client.get("/")
    assert response.status_code == 200
    assert "Database Model" in response.content.decode()
    assert response.context["products"]["p1"]["slug"] == "manstore-m2223"
    assert response.context["products"]["p4"]["slug"] == "olaf-benz-red2059"


def test_home_empty_catalog_has_no_invented_products(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.context["products"] == {}
    assert 'id="p1-img"' not in response.content.decode()


def test_product_detail_is_orm_backed_and_has_exact_variant_gallery(client, django_assert_num_queries):
    call_command("seed_demo_catalog")
    product = Product.objects.get(slug="manstore-m2223")
    ProductImage.objects.create(product=product, color_code="navy", image_url="https://example.test/navy.jpg",
                               alt_key="catalog.photo.demo", position=0)
    url = reverse("catalog:detail", kwargs={"slug": product.slug})
    with django_assert_num_queries(9):
        response = client.get(url)
    data = response.context["product"]
    assert data["name"] == product.model_name
    assert data["galleries"]["navy"] == ["https://example.test/navy.jpg"]
    assert "navy.jpg" not in data["galleries"]["black"][0]
    assert {row["size"] for row in data["variants"]} == {"S", "M", "L", "XL"}
    assert all(row["available"] is False for row in data["variants"] if row["size"] == "XL")
    assert response.context["products"] == {"pdp": data}


def test_unavailable_and_unknown_products_are_not_published(client):
    call_command("seed_demo_catalog")
    Product.objects.filter(slug="manstore-m2223").update(is_active=False)
    for slug in ("manstore-m2223", "missing"):
        assert client.get(reverse("catalog:detail", kwargs={"slug": slug})).status_code == 404


def test_product_without_variants_has_no_fake_selection(client):
    call_command("seed_demo_catalog")
    ProductVariant.objects.filter(product__slug="manstore-m2223").delete()
    response = client.get(reverse("catalog:detail", kwargs={"slug": "manstore-m2223"}))
    assert response.status_code == 200
    assert response.context["product"]["variants"] == []
    assert response.context["product"]["default_size"] == ""
