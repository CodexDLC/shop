from types import SimpleNamespace

import pytest
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.utils.translation import override

from web.localization import translate_text


@pytest.mark.django_db
@pytest.mark.parametrize('language', ['de', 'ru'])
@pytest.mark.parametrize(
    ('template', 'context', 'expected_key'),
    [
        ('cart/includes/test_notice.html', {'cart': {'stock_mode': 'demo'}}, 'commerce.test.notice'),
        ('cart/includes/test_notice.html', {'cart': {'stock_mode': 'inventory_test'}}, 'commerce.test.inventory_notice'),
        ('payments/review.html', {'cart': {'stock_mode': 'inventory_test'}}, 'commerce.test.inventory_notice'),
        ('orders/confirmation.html', {'order': {'stock_mode': 'inventory_test'}, 'cart': {'stock_mode': 'demo'}}, 'commerce.test.inventory_order_notice'),
        ('orders/confirmation.html', {'order': {'stock_mode': 'demo'}, 'cart': {'stock_mode': 'inventory_test'}}, 'commerce.test.notice'),
    ],
)
def test_notice_uses_persisted_order_mode_or_cart_mode(language, template, context, expected_key):
    request = RequestFactory().get('/')
    request.user = SimpleNamespace(is_authenticated=False)
    with override(language):
        rendered = render_to_string(template, context, request=request)
        assert translate_text(expected_key) in rendered
        for key in ('commerce.test.inventory_notice', 'commerce.test.inventory_order_notice', 'commerce.test.notice'):
            if key != expected_key:
                assert translate_text(key) not in rendered
        assert '[commerce.test.' not in rendered


@pytest.mark.django_db
@pytest.mark.parametrize('language', ['de', 'ru'])
@pytest.mark.parametrize('suffix', ['unconfigured', 'shortage', 'retry', 'unavailable'])
def test_inventory_errors_have_localized_customer_text(language, suffix):
    key = f'commerce.error.inventory_{suffix}'
    with override(language):
        text = translate_text(key)
        assert text != f'[{key}]'
        if language == 'ru':
            with override('de'):
                assert text != translate_text(key)
