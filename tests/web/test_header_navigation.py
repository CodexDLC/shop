"""Shared header links work without demo JavaScript; disclosure remains native."""
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest
from django.core.management import call_command
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import override

from web.catalog.models import Brand, Product, ProductVariant

pytestmark = pytest.mark.django_db


class HeaderElements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


@pytest.fixture
def populated_navigation():
    call_command("seed_demo_catalog")
    Product.objects.update(new_until=timezone.localdate())
    ProductVariant.objects.update(is_on_sale=True)
    category = Product.objects.first().category
    category.section = "swimwear"
    category.save(update_fields=["section"])


def test_header_links_are_explicit_real_destinations_with_one_visibility_query(populated_navigation, django_assert_num_queries):
    with override("de"), django_assert_num_queries(1):
        html = render_to_string("includes/header.html")
        root = reverse("catalog:list")
        expected = [root + "?new=1", root + "?section=underwear", root + "?section=swimwear",
                    reverse("catalog:brands"), root + "?sale=1"]
    elements = HeaderElements(html).elements
    anchors = [attrs for tag, attrs in elements if tag == "a"]
    for url in expected:
        assert sum(anchor.get("href") == url for anchor in anchors) == 2
    assert all("data-real-navigation" in anchor for anchor in anchors)
    assert any(anchor["href"] == "/konto/" for anchor in anchors)
    assert any(anchor["href"] == "/katalog/#catalog-query" for anchor in anchors)
    assert all(not anchor["href"].startswith("#") for anchor in anchors)
    assert "top-1 right-1 w-2 h-2" not in html


def test_mobile_navigation_has_native_disclosure_and_real_wishlist():
    html = render_to_string("includes/header.html")
    elements = HeaderElements(html).elements
    details = [attrs for tag, attrs in elements if tag == "details"]
    assert len(details) == 1
    assert "open" not in details[0]
    assert "data-header-menu" in details[0]
    summary = next(attrs for tag, attrs in elements if tag == "summary")
    assert summary["aria-controls"] == "shop-mobile-navigation"
    assert any(attrs.get("id") == "shop-mobile-navigation" for _, attrs in elements)
    assert all("disabled" in attrs for tag, attrs in elements if tag == "button")
    assert reverse("wishlist:detail") in html
    assert "Warenkorb" in html
    assert reverse("cart:detail") in html


def test_header_destinations_respect_language_prefix(populated_navigation):
    with override("ru"):
        html = render_to_string("includes/header.html")
    assert 'href="/ru/katalog/?section=underwear"' in html
    assert 'href="/ru/marken/"' in html
    assert 'href="/ru/konto/"' in html


def test_catalog_preserves_navigation_filters_in_real_form(client):
    response = client.get(reverse("catalog:list"), {"section": "swimwear", "new": "1", "sale": "1"})
    elements = HeaderElements(response.content.decode()).elements
    hidden = {attrs["name"]: attrs["value"] for tag, attrs in elements
              if tag == "input" and attrs.get("type") == "hidden" and attrs.get("name") in {"section", "new", "sale"}}
    assert hidden == {"section": "swimwear", "new": "1", "sale": "1"}
    assert response.context["catalog_heading_key"] == "catalog.heading.new"
    assert "Neuheiten" in response.content.decode()


def test_brand_directory_renders_actual_names_escaped_and_links(client):
    call_command("seed_demo_catalog")
    brand = Brand.objects.first()
    brand.name = '<script>alert("brand")</script>'
    brand.save(update_fields=["name"])
    response = client.get(reverse("catalog:brands"))
    html = response.content.decode()
    assert '&lt;script&gt;alert' in html
    assert '<script>alert("brand")</script>' not in html
    assert reverse("catalog:list") + "?brand=" + brand.slug in html
    assert response.context["brand_links"]


def test_brand_directory_without_visible_products_is_honestly_empty(client):
    response = client.get(reverse("catalog:brands"))
    assert "Noch keine Marken im Sortiment vorhanden." in response.content.decode()
    assert response.context["brand_links"] == []


def test_mobile_disclosure_escape_link_and_outside_close_behavior():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node runtime required for shared navigation behavior")
    script = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const handlers = {}, documentHandlers = {}, attributes = {};
let focused = false;
const summary = {setAttribute: (key, value) => attributes[key] = value, focus: () => focused = true};
const menu = {open: false, querySelector: () => summary, contains: target => target.inside,
 addEventListener: (event, handler) => handlers[event] = handler};
const document = {querySelectorAll: () => [menu], addEventListener: (event, handler) => documentHandlers[event] = handler};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), {document});
assert.equal(attributes['aria-expanded'], 'false');
menu.open = true; handlers.toggle(); assert.equal(attributes['aria-expanded'], 'true');
let prevented = false;
handlers.keydown({key: 'Escape', preventDefault: () => prevented = true, stopPropagation() {}});
assert.equal(menu.open, false); assert.equal(focused, true); assert.equal(prevented, true);
menu.open = true; handlers.click({target: {closest: () => ({})}}); assert.equal(menu.open, false);
menu.open = true; documentHandlers.pointerdown({target: {inside: true}}); assert.equal(menu.open, true);
documentHandlers.pointerdown({target: {inside: false}}); assert.equal(menu.open, false);
menu.open = true; documentHandlers.focusin({target: {inside: false}}); assert.equal(menu.open, false);
'''
    source = Path(__file__).resolve().parents[2] / "src/web/static/storefront/header-navigation.js"
    result = subprocess.run([node, "-e", script, str(source)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
