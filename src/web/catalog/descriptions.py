import re

from web.localization import translate_text


def legacy_description(product):
    """Resolve preserved catalogue keys without exposing missing-key markers."""
    key = product.description_key
    if not key or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*', key):
        return ''
    value = translate_text(key).strip()
    return value if value not in (key, f'[{key}]') else ''
