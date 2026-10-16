import pytest
from django.core.management import call_command
from django.urls import reverse

from web.catalog.models import ProductVariant

pytestmark = pytest.mark.django_db


def test_manual_preview_returns_demo_sku_price_gallery_without_mutation(client):
    call_command("seed_demo_catalog")
    url = reverse("catalog:variant_preview", kwargs={"slug": "manstore-m2223"})
    response = client.get(url, {"color": "black", "size": "M"})
    assert response.status_code == 200
    body = response.json()
    assert body["variant"]["sku"] == "DEMO-MANSTORE-M2223-BLACK-M"
    assert body["variant"]["price"] == "49.95"
    assert body["gallery"]["images"]
    assert body["checkout_enabled"] is False
    assert response["Cache-Control"] == "no-store"
    assert response["X-Robots-Tag"] == "noindex"
    assert ProductVariant.objects.count() == 32
    assert client.post(url, {"color": "black", "size": "M"}).status_code == 405


@pytest.mark.parametrize("params,status,code", [
    ({}, 400, "catalog.selection_required"),
    ({"color": "black", "size": "XXXL"}, 404, "catalog.variant_not_found"),
])
def test_preview_errors_have_safe_translated_messages(client, params, status, code):
    call_command("seed_demo_catalog")
    response = client.get(reverse("catalog:variant_preview", kwargs={"slug": "manstore-m2223"}), params)
    assert response.status_code == status
    error = response.json()["error"]
    assert error["code"] == code
    assert error["message"] and not error["message"].startswith("[")


def test_sold_out_size_remains_visible_but_unavailable(client):
    call_command("seed_demo_catalog")
    response = client.get(reverse("catalog:variant_preview", kwargs={"slug": "manstore-m2223"}),
                          {"color": "black", "size": "XL"})
    assert response.status_code == 200
    assert response.json()["variant"]["demo_available"] is False
