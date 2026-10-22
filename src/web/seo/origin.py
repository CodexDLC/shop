import re
from urllib.parse import urlsplit

from django.conf import settings


def public_origin():
    """Return a configured public HTTPS origin, never a request-derived host."""
    value = getattr(settings, 'SEO_PUBLIC_ORIGIN', '')
    if not isinstance(value, str) or not value or re.search(r'[\s\\]', value):
        return ''
    try:
        parts = urlsplit(value)
        host = parts.hostname or ''
        if (parts.scheme != 'https' or parts.username or parts.password or parts.port not in (None, 443)
                or parts.path not in ('', '/') or parts.query or parts.fragment
                or not re.fullmatch(r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+'
                                    r'[a-zA-Z]{2,63}', host)
                or host.lower().endswith(('.localhost', '.local', '.internal', '.test', '.invalid'))):
            return ''
    except ValueError:
        return ''
    return f'https://{host.lower()}'


def indexing_enabled():
    return bool(getattr(settings, 'SEO_INDEXING_ENABLED', False)
                and not getattr(settings, 'SEO_FORCE_NOINDEX', False) and public_origin())
