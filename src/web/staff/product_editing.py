"""Staff editing contract. Mutations must hold the parent product row lock."""
import hashlib
import json

from django.core import signing
from django.core.exceptions import PermissionDenied
from django.utils.translation import override


def require_editable(product):
    if product.is_active:
        raise PermissionDenied('Published products must be explicitly withdrawn before editing.')


def mark_changed(product):
    require_editable(product)
    product.editorial_state = 'draft'
    product.review_fingerprint = ''
    product.save(update_fields=['editorial_state', 'review_fingerprint'])


def content_fingerprint(product):

    from web.catalog.descriptions import legacy_description

    ignored = {'editorial_state', 'review_fingerprint', 'is_active', 'published_at'}
    state = {field.attname: str(getattr(product, field.attname))
             for field in product._meta.concrete_fields if field.name not in ignored}
    with override('de'):
        state['legacy_description'] = legacy_description(product)
    if product.pk:
        for name in ('tags', 'materials', 'properties'):
            state[name] = list(getattr(product, name).order_by('pk').values())
        for name in ('brand', 'category'):
            related_model = product._meta.get_field(name).remote_field.model
            state[f'{name}_reference'] = related_model.objects.filter(
                pk=getattr(product, f'{name}_id'),
            ).values().first()
        for name in ('information', 'variants', 'images'):
            state[name] = list(getattr(product, name).order_by('pk').values())
    return hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()


def issue_state(product):
    return signing.dumps([product.pk, content_fingerprint(product), product.is_active,
                          product.editorial_state, product.review_fingerprint], salt='staff-product-state')


def check_state(product, token):
    try:
        submitted = signing.loads(token, salt='staff-product-state', max_age=7200)
    except signing.BadSignature:
        return False
    return submitted == [product.pk, content_fingerprint(product), product.is_active,
                         product.editorial_state, product.review_fingerprint]


def publication_issues(product):
    """Actual persisted content, including every presented colour and shared gallery."""
    from web.catalog.descriptions import legacy_description

    issues = []
    if not all((product.model_name.strip(), product.slug.strip(), product.brand_id, product.category_id)):
        issues.append('staff.workflow.missing_base')
    information = product.information.filter(language_code='de').first()
    with override('de'):
        has_legacy_description = legacy_description(product)
    if not ((information and information.description.strip()) or has_legacy_description):
        issues.append('staff.workflow.missing_description')
    variants = list(product.variants.filter(is_active=True))
    if not variants or any(not row.sku.strip() or row.currency != 'EUR'
                           or not row.price.is_finite() or row.price <= 0 for row in variants):
        issues.append('staff.workflow.missing_variant')
    images = [image for image in product.images.all() if image.public_url]
    if not images or any(not any(image.color_code in ('', row.color_code) for image in images)
                         for row in variants):
        issues.append('staff.workflow.missing_images')
    return issues
