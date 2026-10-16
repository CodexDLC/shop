import pytest
from django.core.management import call_command
from django.test import Client


@pytest.fixture(autouse=True)
def catalog_seed(db):
    call_command("seed_demo_catalog")


def test_homepage_renders_local_demo_without_external_operations():
    response = Client().get("/")
    assert response.status_code == 200
    html = response.content.decode()
    assert "Männermasche" in html
    assert "/static/storefront/assets" not in html
    assert "data-purpose=\"hero" in html or "hero-blend-gradient" in html
    assert "MANSTORE" in html
    assert "Designvorschau" in html
    assert 'id="quick-view-modal"' in html or 'id="quickViewModal"' in html
    assert 'data-shared-chrome="header"' in html
    assert 'data-shop-photo="true"' in html
    assert "M2223 Bungee Pants" in html


def test_homepage_does_not_accept_purchase_posts():
    assert Client().post("/").status_code == 405
