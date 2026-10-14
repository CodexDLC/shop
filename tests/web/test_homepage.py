from django.test import Client


def test_homepage_renders_local_demo_without_external_operations():
    response = Client().get("/")
    assert response.status_code == 200
    html = response.content.decode()
    assert "Männermasche" in html
    assert "hero.png" in html
    assert "MANSTORE" in html
    assert "Designvorschau" in html
    assert "<dialog" in html


def test_homepage_does_not_accept_purchase_posts():
    assert Client().post("/").status_code == 405
