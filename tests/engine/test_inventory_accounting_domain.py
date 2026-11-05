from dataclasses import FrozenInstanceError

import pytest

from codex_ecommerce.inventory import (
    InvalidQuantityError,
    InventoryInvariantError,
    OperationContext,
    StaleRevisionError,
    StockKey,
    StockNotConfiguredError,
    StockSnapshot,
    adjust_stock,
    initialize_stock,
    receive_stock,
)


def context(revision=0):
    return OperationContext('key', 'staff', '1', 'Counted stock', revision)


def test_explicit_zero_and_immutable_calculations():
    initial = initialize_stock(StockKey('1', 'main'), 0, context())
    assert (initial.on_hand, initial.reserved, initial.revision) == (0, 0, 1)
    received = receive_stock(initial, 7, context(1))
    adjusted = adjust_stock(received, 4, context(2))
    assert initial.on_hand == 0 and received.on_hand == 7
    assert (adjusted.on_hand, adjusted.revision) == (4, 3)
    with pytest.raises(FrozenInstanceError):
        adjusted.on_hand = 8


@pytest.mark.parametrize('command', [receive_stock, adjust_stock])
def test_missing_stock_and_revision_are_explicit(command):
    with pytest.raises(StockNotConfiguredError):
        command(None, 1, context())
    with pytest.raises(StaleRevisionError):
        command(StockSnapshot(StockKey('1', 'main'), 5, 2, 4), 3, context(3))


def test_adjust_cannot_erase_reservations():
    stock = StockSnapshot(StockKey('1', 'main'), 7, 3, 2)
    with pytest.raises(InventoryInvariantError):
        adjust_stock(stock, 2, context(2))
    assert adjust_stock(stock, 3, context(2)).reserved == 3


@pytest.mark.parametrize('quantity', [-1, True, 1.5, '1', None])
@pytest.mark.parametrize('command', [initialize_stock, receive_stock, adjust_stock])
def test_reject_invalid_quantity(command, quantity):
    arg = StockKey('1', 'main') if command is initialize_stock else StockSnapshot(StockKey('1', 'main'), 1, 0, 0)
    with pytest.raises(InvalidQuantityError):
        command(arg, quantity, context())


def test_receipt_positive_and_initialize_revision_zero():
    with pytest.raises(InvalidQuantityError):
        receive_stock(StockSnapshot(StockKey('1', 'main'), 0, 0, 0), 0, context())
    with pytest.raises(StaleRevisionError):
        initialize_stock(StockKey('1', 'main'), 0, context(1))
    with pytest.raises(InventoryInvariantError):
        initialize_stock(StockKey('1', 'main'), 0, object())
