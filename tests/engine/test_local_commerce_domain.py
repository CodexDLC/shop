from decimal import Decimal

import pytest

from codex_ecommerce.cart import CartError, CartItem, quote_total, validate_quantity


def test_decimal_quote_is_exact_and_immutable():
    row = CartItem('SKU', 3, Decimal('0.10'), 'EUR', 5)
    assert quote_total((row,)) == Decimal('0.30')
    with pytest.raises(AttributeError):
        row.quantity = 2


@pytest.mark.parametrize('value', [True, False, -1, 0, '1.1', '1e1', '21', '１２', None])
def test_quantity_contract(value):
    with pytest.raises(CartError):
        validate_quantity(value)


@pytest.mark.parametrize('changes', [
    {'unit_amount': Decimal('-0.01')}, {'unit_amount': Decimal('NaN')},
    {'unit_amount': 0.1}, {'unit_amount': Decimal('0.001')},
    {'currency': 'USD'}, {'available_quantity': 0},
])
def test_quote_rejects_invalid_money_and_availability(changes):
    data = {'sku': 'SKU', 'quantity': 1, 'unit_amount': Decimal('1.00'), 'currency': 'EUR',
            'available_quantity': 10}
    with pytest.raises(CartError):
        quote_total((CartItem(**(data | changes)),))


def test_duplicate_sku_and_line_limit():
    row = CartItem('SKU', 1, Decimal('1.00'), 'EUR', 10)
    with pytest.raises(CartError):
        quote_total((row, row))
    with pytest.raises(CartError):
        quote_total(tuple(CartItem(str(i), 1, Decimal('1.00'), 'EUR', 10) for i in range(51)))


def test_quote_rejects_total_outside_order_money_capacity():
    items = tuple(CartItem(str(i), 20, Decimal('99999999.99'), 'EUR', 20) for i in range(50))
    with pytest.raises(CartError):
        quote_total(items)
