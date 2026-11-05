from datetime import datetime

from .invalid_quantity import InvalidQuantityError
from .inventory_invariant import InventoryInvariantError


def nonnegative_int(value):
    if type(value) is not int or value < 0:
        raise InvalidQuantityError()


def identifier(value):
    if not isinstance(value, str) or not value.strip():
        raise InventoryInvariantError()


def aware_datetime(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise InventoryInvariantError()
