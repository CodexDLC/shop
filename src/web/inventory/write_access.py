from contextlib import contextmanager
from contextvars import ContextVar

from django.core.exceptions import PermissionDenied

_writing = ContextVar('inventory_service_write', default=False)


def require_service_write():
    if not _writing.get():
        raise PermissionDenied('Inventory mutations require the inventory service.')


@contextmanager
def service_write():
    token = _writing.set(True)
    try:
        yield
    finally:
        _writing.reset(token)
