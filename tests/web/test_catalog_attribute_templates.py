from urllib.parse import parse_qs, urlparse

import pytest
from django.core.management import call_command
from django.http import QueryDict
from django.urls import reverse

from tests.web.test_catalog_listing_templates import ListingParser
from web.catalog.listing_context import ListingContext
from web.catalog.listing_request import ListingRequest

pytestmark = pytest.mark.django_db


def test_new_filters_are_real_get_controls_and_unknown_selection_survives(client):
    response = client.get(reverse('catalog:list'), {'material': 'missing-material', 'property': 'missing-property',
                                                   'sort': 'newest'})
    elements = ListingParser(response.content.decode()).elements
    for name, value in [('material', 'missing-material'), ('property', 'missing-property')]:
        control = next((attrs for tag, attrs in elements if tag == 'input' and attrs.get('name') == name), None)
        assert control is not None
        assert control['value'] == value
        assert control['form'] == 'catalog-filters'
        assert 'checked' in control and 'disabled' not in control
    assert not any(tag == 'fieldset' and 'disabled' in attrs for tag, attrs in elements)
    options = [attrs for tag, attrs in elements if tag == 'option']
    newest = next(attrs for attrs in options if attrs.get('value') == 'newest')
    assert 'selected' in newest and 'disabled' not in newest
    assert any(attrs.get('value') == 'rating' and 'disabled' not in attrs for attrs in options)
    assert any(attrs.get('value') == 'popular' and 'disabled' in attrs for attrs in options)


def test_popularity_cannot_be_forced_through_url(client):
    response = client.get(reverse('catalog:list'), {'sort': 'popular'})
    listing = response.context['catalog_listing']
    assert listing['sort'] == 'name'
    assert 'catalog.listing.error.invalid_sort' in listing['errors']


@pytest.mark.parametrize('sort', ['newest', 'rating'])
def test_attributes_survive_pagination_and_chip_removal_without_broadening(sort, django_assert_num_queries):
    from web.catalog.models import Material, Product, ProductProperty, ProductVariant

    call_command('seed_demo_catalog')
    sample = Product.objects.first()
    material = Material.objects.create(slug='cotton', name='Cotton')
    trait = ProductProperty.objects.create(slug='light', name='Light')
    for number in range(14):
        item = Product.objects.create(slug=f'attribute-{number}', model_name=f'Attribute {number:02}',
                                      brand=sample.brand, category=sample.category)
        item.materials.add(material)
        item.properties.add(trait)
        ProductVariant.objects.create(product=item, sku=f'ATTRIBUTE-{number}', color_code='black',
                                      size='M', price=20)
    with django_assert_num_queries(12):
        listing = ListingContext(ListingRequest.from_query(QueryDict(
            f'material=cotton&property=light&sort={sort}',
        ))).build()
    assert listing['total'] == 14
    assert parse_qs(urlparse(listing['next_url']).query) == {
        'material': ['cotton'], 'property': ['light'], 'sort': [sort], 'page': ['2'],
    }
    chip = next(chip for chip in listing['active_filters'] if chip['value'] == 'cotton')
    assert chip['label'] == 'Cotton'
    assert parse_qs(urlparse(chip['remove_url']).query) == {'property': ['light'], 'sort': [sort]}
    with django_assert_num_queries(12):
        single = ListingContext(ListingRequest.from_query(QueryDict(
            f'q=Attribute+00&material=cotton&property=light&sort={sort}',
        ))).build()
        assert single['total'] == 1


@pytest.mark.parametrize('name,model_name,facet,relation', [
    ('material', 'Material', 'materials', 'materials'), ('property', 'ProductProperty', 'properties', 'properties'),
])
def test_selected_attributes_beyond_facet_cap_remain_form_controls(client, name, model_name, facet, relation):
    from web.catalog import models

    call_command('seed_demo_catalog')
    product = models.Product.objects.first()
    model = getattr(models, model_name)
    rows = model.objects.bulk_create([model(slug=f'v-{number:03}', name=f'Name {number:03}') for number in range(202)])
    getattr(product, relation).add(*rows)
    response = client.get(reverse('catalog:list'), {name: rows[-1].slug, 'sort': 'rating'})
    listing = response.context['catalog_listing']
    assert listing['total'] == 1
    assert len(listing['facets'][facet]) == 201
    selected = next(row for row in listing['facets'][facet] if row['value'] == rows[-1].slug)
    assert selected['selected'] is True
    elements = ListingParser(response.content.decode()).elements
    assert any(tag == 'input' and attrs.get('name') == name and attrs.get('value') == rows[-1].slug
               and 'checked' in attrs for tag, attrs in elements)


def test_attribute_names_are_escaped_in_filters_and_chips(client):
    from web.catalog.models import Material, Product

    call_command('seed_demo_catalog')
    material = Material.objects.create(slug='unsafe', name='<script>material()</script>')
    Product.objects.first().materials.add(material)
    html = client.get(reverse('catalog:list'), {'material': material.slug}).content.decode()
    assert '&lt;script&gt;material()&lt;/script&gt;' in html
    assert '<script>material()</script>' not in html
