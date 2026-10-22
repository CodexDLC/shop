import pytest
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from web.catalog.models import Product, ProductInformation

pytestmark = pytest.mark.django_db


@pytest.fixture
def publication(client, django_user_model):
    call_command('seed_demo_catalog')
    product = Product.objects.first()
    product.is_active = False
    product.save(update_fields=['is_active'])
    ProductInformation.objects.create(product=product, language_code='de', description='Echte Beschreibung')
    user = django_user_model.objects.create_user(username='publisher', is_staff=True)
    user.user_permissions.add(*Permission.objects.filter(content_type__app_label='catalog'))
    client.force_login(user)
    return client, user, product


def workflow_post(client, product, action, token=None):
    url = reverse('staff:product_publication', kwargs={'pk': product.pk})
    if token is None:
        token = client.get(url).context['original_state']
    return client.post(url, {'action': action, 'original_state': token})


def test_review_publish_withdraw_and_duplicate_actions(publication):
    client, _, product = publication
    response = workflow_post(client, product, 'review')
    assert response.status_code == 302
    product.refresh_from_db()
    assert product.editorial_state == 'review' and not product.is_active
    token = client.get(reverse('staff:product_publication', kwargs={'pk': product.pk})).context['original_state']
    assert workflow_post(client, product, 'publish', token).status_code == 302
    product.refresh_from_db()
    assert product.is_active and product.published_at is not None
    published_at = product.published_at
    assert workflow_post(client, product, 'publish', token).status_code == 409
    assert workflow_post(client, product, 'withdraw').status_code == 302
    product.refresh_from_db()
    assert not product.is_active and product.editorial_state == 'draft'
    assert product.published_at == published_at


def test_changed_information_or_image_invalidates_review(publication):
    client, _, product = publication
    assert workflow_post(client, product, 'review').status_code == 302
    product.information.update(description='Geändert außerhalb des Editors')
    assert workflow_post(client, product, 'publish').status_code == 409
    product.refresh_from_db()
    assert not product.is_active
    assert workflow_post(client, product, 'review').status_code == 302
    product.images.all().delete()
    assert workflow_post(client, product, 'publish').status_code == 409


def test_incomplete_review_and_separate_publish_permission(publication):
    client, user, product = publication
    product.information.all().delete()
    product.description_key = ''
    product.save(update_fields=['description_key'])
    assert workflow_post(client, product, 'review').status_code == 400
    product.refresh_from_db()
    assert not product.is_active
    user.user_permissions.remove(Permission.objects.get(content_type__app_label='catalog', codename='publish_product'))
    assert workflow_post(client, product, 'publish').status_code == 403


def test_private_preview_draft_and_gets_never_write(publication, django_assert_num_queries):
    client, user, product = publication
    before = Product.objects.values().get(pk=product.pk)
    assert client.get(reverse('catalog:detail', kwargs={'slug': product.slug})).status_code == 404
    response = client.get(reverse('staff:product_preview', kwargs={'pk': product.pk}))
    assert response.status_code == 200
    assert 'no-store' in response['Cache-Control'] and 'noindex' in response['X-Robots-Tag']
    assert b'Echte Beschreibung' in response.content
    assert client.get(reverse('staff:product_publication', kwargs={'pk': product.pk})).status_code == 200
    assert Product.objects.values().get(pk=product.pk) == before
    client.logout()
    assert client.get(reverse('staff:product_preview', kwargs={'pk': product.pk})).status_code in (302, 403)


def test_published_write_guard_and_csrf(publication):
    client, user, product = publication
    product.is_active = True
    product.save(update_fields=['is_active'])
    assert client.post(reverse('staff:product_edit', kwargs={'pk': product.pk}), {}).status_code == 403
    assert client.post(reverse('staff:variants', kwargs={'pk': product.pk}), {}).status_code == 403
    csrf = Client(enforce_csrf_checks=True)
    csrf.force_login(user)
    assert workflow_post(csrf, product, 'withdraw').status_code == 403


def test_workflow_models_are_read_only_in_django_admin(publication):
    from django.contrib import admin
    from django.test import RequestFactory

    from web.catalog.models import Brand, ProductImage, ProductVariant

    client, user, product = publication
    request = RequestFactory().get('/admin/')
    request.user = user
    for model in (Product, ProductImage, ProductVariant, ProductInformation):
        model_admin = admin.site._registry[model]
        assert model_admin.has_view_permission(request)
        assert not model_admin.has_add_permission(request)
        assert not model_admin.has_change_permission(request)
        assert not model_admin.has_delete_permission(request)
        assert client.post(reverse(f'admin:catalog_{model._meta.model_name}_add'), {}).status_code == 403
    assert admin.site._registry[Brand].has_change_permission(request)
    assert client.get(reverse('admin:catalog_product_change', args=[product.pk])).status_code == 200
    assert client.post(reverse('admin:catalog_product_change', args=[product.pk]), {}).status_code == 403


def test_information_save_stale_guard_and_review_reset(publication):
    from web.staff.product_editing import issue_state

    client, _, product = publication
    url = reverse('staff:product_information', kwargs={'pk': product.pk})
    assert workflow_post(client, product, 'review').status_code == 302
    product.refresh_from_db()
    token = issue_state(product)
    data = {'original_state': token, 'description': 'Neuer Text <script>untrusted</script>',
            'composition': '95% Baumwolle', 'care': '30 Grad'}
    assert client.post(url, data).status_code == 302
    product.refresh_from_db()
    assert product.editorial_state == 'draft' and not product.review_fingerprint
    assert product.information.get(language_code='de').composition == '95% Baumwolle'
    assert client.post(url, data).status_code == 409
    response = client.get(reverse('staff:product_preview', kwargs={'pk': product.pk}))
    assert b'&lt;script&gt;untrusted&lt;/script&gt;' in response.content
    assert b'<script>untrusted</script>' not in response.content
    assert b'data-product-action' not in response.content
    assert b'data-wishlist-product' not in response.content


def test_private_variant_preview_does_not_expose_draft_publicly(publication):
    client, _, product = publication
    variant = product.variants.first()
    params = {'color': variant.color_code, 'size': variant.size}
    private = reverse('staff:product_variant_preview', kwargs={'pk': product.pk})
    assert client.get(private, params).status_code == 200
    assert client.get(reverse('catalog:variant_preview', kwargs={'slug': product.slug}), params).status_code == 404
    client.logout()
    assert client.get(private, params).status_code in (302, 403)


@pytest.mark.parametrize('problem', ['zero_price', 'non_eur', 'no_active_sku', 'missing_color'])
def test_review_checks_actual_active_variant_and_colour_gallery(publication, problem):
    from web.catalog.models import ProductImage

    client, _, product = publication
    variant = product.variants.first()
    if problem == 'zero_price':
        product.variants.filter(pk=variant.pk).update(price=0)
    elif problem == 'non_eur':
        product.variants.filter(pk=variant.pk).update(currency='USD')
    elif problem == 'no_active_sku':
        product.variants.update(is_active=False)
    else:
        product.images.all().delete()
        ProductImage.objects.create(product=product, color_code='unrepresented-colour',
                                    image_url='https://example.test/other.jpg')
    assert workflow_post(client, product, 'review').status_code == 400
    product.refresh_from_db()
    assert not product.is_active and not product.review_fingerprint


def test_existing_published_product_get_preserves_visibility_and_unknown_date(publication):
    client, _, product = publication
    product.is_active = True
    product.save(update_fields=['is_active'])
    assert product.published_at is None
    for name in ('product_edit', 'product_publication', 'product_information', 'variants'):
        assert client.get(reverse(f'staff:{name}', kwargs={'pk': product.pk})).status_code == 200
    product.refresh_from_db()
    assert product.is_active and product.published_at is None
    assert client.get(reverse('catalog:detail', kwargs={'slug': product.slug})).status_code == 200


@pytest.mark.parametrize('record', ['missing', 'blank'])
def test_legacy_description_is_displayed_in_public_and_private_pdp(publication, record):
    from web.localization import translate_text
    from web.staff.product_editing import publication_issues

    client, _, product = publication
    expected = translate_text(product.description_key)
    assert expected and expected != f'[{product.description_key}]'
    if record == 'missing':
        product.information.all().delete()
    else:
        product.information.update(description='   ')
    assert 'staff.workflow.missing_description' not in publication_issues(product)
    private = client.get(reverse('staff:product_preview', kwargs={'pk': product.pk}))
    assert private.context['product_information']['description'] == expected
    assert expected.encode() in private.content
    product.is_active = True
    product.save(update_fields=['is_active'])
    public = client.get(reverse('catalog:detail', kwargs={'slug': product.slug}))
    assert public.context['product_information']['description'] == expected
    assert expected.encode() in public.content
    product.description_key = 'unknown.legacy.description'
    product.save(update_fields=['description_key'])
    unknown = client.get(reverse('catalog:detail', kwargs={'slug': product.slug}))
    assert unknown.context['product_information']['description'] == ''
    assert b'[unknown.legacy.description]' not in unknown.content


def test_changed_legacy_translation_invalidates_checked_contents(publication, monkeypatch):
    from web.catalog import descriptions

    client, _, product = publication
    product.information.all().delete()
    assert workflow_post(client, product, 'review').status_code == 302
    original_translate = descriptions.translate_text
    monkeypatch.setattr(descriptions, 'translate_text', lambda key: (
        'Eine inzwischen geänderte Beschreibung' if key == product.description_key else original_translate(key)
    ))
    assert workflow_post(client, product, 'publish').status_code == 409
    product.refresh_from_db()
    assert not product.is_active
