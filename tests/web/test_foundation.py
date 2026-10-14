from django.conf import settings
from django.test import Client


def test_web_uses_engine_without_enabling_integrations():
    response = Client().get("/health/")
    assert response.status_code == 200
    assert response.json()["payments_enabled"] is False
    assert response.json()["ebay_write_enabled"] is False


def test_booking_is_not_installed():
    assert all("booking" not in app for app in settings.INSTALLED_APPS)


def test_health_does_not_accept_mutations():
    assert Client().post("/health/").status_code == 405
