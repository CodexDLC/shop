import re

from codex_ecommerce.inventory import InventoryInvariantError


def require_reference(value):
    """Constrain operational references; email/URL/request content is not an ID."""
    if not isinstance(value, str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}', value) is None:
        raise InventoryInvariantError()
    return value
