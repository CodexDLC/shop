"""Rendered catalog contracts: real forms, safe data and consistent listing routes."""
import json
from html.parser import HTMLParser

import pytest
from django.core.management import call_command
from django.urls import reverse

from web.catalog.models import Product

pytestmark = pytest.mark.django_db


class ListingParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def test_listing_has_real_get_form_and_preserves_filter_values(client):
    call_command("seed_demo_catalog")
    response = client.get(reverse("catalog:list"), {"q": "MANSTORE", "size": "M", "sort": "price_asc"})
    elements = ListingParser(response.content.decode()).elements
    forms = [attrs for tag, attrs in elements if tag == "form" and attrs.get("id") == "catalog-filters"]
    assert len(forms) == 1
    assert forms[0]["method"] == "get"
    assert forms[0]["action"] == reverse("catalog:list")
    assert "data-real-catalog" in forms[0]
    query = next(attrs for tag, attrs in elements if tag == "input" and attrs.get("name") == "q")
    assert query["value"] == "MANSTORE"
    assert query["form"] == "catalog-filters"
    size = next(attrs for tag, attrs in elements if tag == "input" and attrs.get("name") == "size" and attrs["value"] == "M")
    assert "checked" in size
    assert all("data-preview-only" in attrs for tag, attrs in elements if tag == "article")


def test_unknown_query_renders_empty_state_without_demo_cards(client):
    call_command("seed_demo_catalog")
    response = client.get(reverse("catalog:list"), {"q": "missing-product-only"})
    html = response.content.decode()
    assert "Keine passenden Produkte gefunden" in html
    assert "data-catalog-product=" not in html
    assert "0–0" in html
    assert f'href="{reverse("catalog:list")}"' in html


def test_orm_product_and_query_are_escaped_and_links_target_actual_model(client):
    call_command("seed_demo_catalog")
    product = Product.objects.first()
    product.model_name = '<script>alert("model")</script>'
    product.save(update_fields=["model_name"])
    response = client.get(reverse("catalog:list"))
    html = response.content.decode()
    assert '&lt;script&gt;alert' in html
    assert '<script>alert("model")</script>' not in html
    assert reverse("catalog:detail", kwargs={"slug": product.slug}) in html
    script = html.split('id="catalog-products" type="application/json">', 1)[1].split('</script>', 1)[0]
    data = json.loads(script)
    assert any(item["name"] == product.model_name for item in data.values())


def test_unsupported_filter_groups_are_disabled_with_explanation(client):
    response = client.get(reverse("catalog:list"))
    elements = ListingParser(response.content.decode()).elements
    disabled = [attrs for tag, attrs in elements if tag == "fieldset" and "disabled" in attrs]
    assert len(disabled) == 2
    assert all(attrs.get("aria-describedby") == "unsupported-filters" for attrs in disabled)
    assert 'id="unsupported-filters"' in response.content.decode()

def test_listing_boot_reuses_snapshot_but_variant_changes_validate_with_server():
    import shutil
    import subprocess
    from pathlib import Path

    node = shutil.which("node")
    if not node:
        pytest.skip("Node runtime is required for the shared browser-script regression")
    script = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(process.argv[1], 'utf8');
async function run(previewOnly, code) {
  let requests = 0;
  const handlers = {};
  const action = {disabled: true, style: {}};
  const root = {
    dataset: {catalogProduct: code},
    hasAttribute: name => previewOnly && name === 'data-preview-only',
    querySelectorAll: selector => selector === '[data-product-action]' ? [action] : [],
    addEventListener: (event, handler) => { handlers[event] = handler; },
    dispatchEvent() {}, contains: () => true,
  };
  const product = {default_color: 'black', default_size: 'M', price: '20.00',
    colors: [{code: 'black', label: 'Black'}, {code: 'navy', label: 'Navy'}], galleries: {},
    variants: [{color: 'black', size: 'M', sku: 'A', price: '20.00', available: true}],
    preview_url: '/variant/'};
  const document = {readyState: 'complete', documentElement: {lang: 'de'},
    querySelectorAll: () => [root], getElementById: id => id === 'catalog-products'
      ? {textContent: JSON.stringify({[code]: product})} : id === 'catalog-selection-texts'
      ? {textContent: '{}'} : null};
  const context = {document, window: {location: {href: 'http://localhost/katalog/'}},
    URL, AbortController, Intl, CustomEvent: class {},
    fetch: async () => { requests++; return {ok: true, json: async () => ({variant:
      {color: 'navy', size: 'M', sku: 'B', price: '21.00', currency: 'EUR', active: true, demo_available: true}})}; }};
  vm.runInNewContext(source, context);
  assert.equal(requests, previewOnly ? 0 : 1);
  if (previewOnly) {
    assert.equal(action.disabled, false);
    const color = {dataset: {color: 'navy'}};
    handlers.click({target: {closest: selector => selector === '[data-color]' ? color : null}});
    assert.equal(requests, 1);
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(root.dataset.selectedSku, 'B');
  }
}
(async () => { await run(true, 'listing-1'); await run(false, 'p1'); await run(false, 'pdp'); })()
  .catch(error => { console.error(error); process.exitCode = 1; });
'''
    source = Path(__file__).resolve().parents[2] / "src/web/static/storefront/catalog-selection.js"
    completed = subprocess.run([node, "-e", script, str(source)], capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
