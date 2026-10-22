from decimal import Decimal

import pytest

from codex_ecommerce.cart import CartError, DiscountRule, discount_amount


def test_percent_rounds_half_up_and_fixed_clamps():
    assert discount_amount(Decimal('10.05'), DiscountRule('percent', Decimal('10'))) == Decimal('1.01')
    assert discount_amount(Decimal('10.05'), DiscountRule('fixed', Decimal('20'))) == Decimal('10.05')
    assert discount_amount(Decimal('0'), DiscountRule('fixed', Decimal('2'))) == Decimal('0.00')


@pytest.mark.parametrize('kind,value,minimum,currency', [
    ('percent', '101', '0', 'EUR'), ('fixed', '0', '0', 'EUR'), ('fixed', '-1', '0', 'EUR'),
    ('fixed', 'NaN', '0', 'EUR'), ('fixed', 'Infinity', '0', 'EUR'),
    ('fixed', '1.001', '0', 'EUR'), ('percent', '2.001', '0', 'EUR'),
    ('fixed', '1', '-1', 'EUR'), ('fixed', '1', '0.001', 'EUR'),
    ('fixed', '1', '0', 'USD'), ('other', '1', '0', 'EUR'),
])
def test_bad_rules_rejected(kind, value, minimum, currency):
    with pytest.raises(CartError):
        discount_amount(Decimal('10'), DiscountRule(kind, Decimal(value), Decimal(minimum), currency))


def test_minimum_and_subtotal_validation():
    with pytest.raises(CartError, match='commerce.error.coupon_minimum'):
        discount_amount(Decimal('9.99'), DiscountRule('percent', Decimal('10'), Decimal('10')))
    for amount in (Decimal('-1'), Decimal('NaN'), Decimal('1.001'), '10.00'):
        with pytest.raises(CartError):
            discount_amount(amount, DiscountRule('fixed', Decimal('1')))
