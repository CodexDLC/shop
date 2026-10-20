import pytest
from django.core.management import call_command
from django.urls import reverse

from web.catalog.models import ProductVariant
from web.catalog.recommendations import collection_suggestions

pytestmark = pytest.mark.django_db


def test_suggestions_are_bounded_real_eur_models_and_exclude_cart(django_assert_num_queries):
    call_command('seed_demo_catalog')
    with django_assert_num_queries(4):
        suggestions = collection_suggestions()
    assert len(suggestions) == 3
    excluded = suggestions[0]
    selected = collection_suggestions(excluded_skus=tuple(row['sku'] for row in excluded['variants']))
    assert excluded['id'] not in {item['id'] for item in selected}
    ProductVariant.objects.filter(product_id=excluded['id']).update(currency='USD')
    assert excluded['id'] not in {item['id'] for item in collection_suggestions()}


def test_cart_help_is_gettable_form_link_not_post_action(client):
    response = client.get(reverse('cart:detail'))
    assert response.status_code == 200
    from django.template.loader import render_to_string
    capsule = render_to_string('cart/includes/help_capsule.html')
    assert f'href="{reverse("support:help")}#kontakt-formular"' in capsule
    assert f'href="{reverse("support:contact")}"' not in capsule
    assert client.get(reverse('support:help')).status_code == 200
