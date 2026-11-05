"""Bounded HTTP invocation of the web-owned inventory expiry service."""
import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from time import monotonic
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

logger = logging.getLogger(__name__)
MAX_BODY = 8192
PATH = '/internal/inventory/expiry/'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def enabled():
    return os.environ.get('INVENTORY_EXPIRY_ENABLED', '') == '1'


def validate_url(url):
    if not isinstance(url, str) or any(ord(c) < 33 or ord(c) == 127 for c in url):
        raise ValueError('invalid expiry URL')
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise ValueError('invalid expiry URL') from None
    if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.path != PATH or parsed.query or parsed.fragment
            or (port is not None and not 1 <= port <= 65535)):
        raise ValueError('invalid expiry URL')
    if parsed.scheme == 'http' and parsed.hostname not in {'localhost', '127.0.0.1', '::1', 'web'}:
        raise ValueError('invalid expiry URL')
    return url


def send_expiry(url, token):
    opener = build_opener(ProxyHandler({}), NoRedirect())
    request = Request(url, data=b'{}', method='POST', headers={
        'Authorization': f'Bearer {token}', 'Content-Type': 'application/json', 'Accept': 'application/json',
    })
    deadline = monotonic() + 8
    with opener.open(request, timeout=8) as response:
        chunks = []
        size = 0
        while True:
            if monotonic() >= deadline:
                raise TimeoutError('response deadline exceeded')
            chunk = response.read1(min(1024, MAX_BODY + 1 - size))
            if monotonic() >= deadline:
                raise TimeoutError('response deadline exceeded')
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_BODY:
                raise ValueError('response too large')
        result = json.loads(b''.join(chunks))
    if (not isinstance(result, dict) or set(result) != {'scanned', 'expired', 'skipped', 'has_more'}
            or any(type(result[k]) is not int or result[k] < 0 for k in ('scanned', 'expired', 'skipped'))
            or any(result[k] > 100 for k in ('scanned', 'expired', 'skipped'))
            or result['expired'] + result['skipped'] != result['scanned']
            or type(result['has_more']) is not bool):
        raise ValueError('invalid response')
    return result


async def inventory_expiry(ctx):
    if not enabled():
        return None
    try:
        url = validate_url(os.environ.get('INVENTORY_EXPIRY_URL', ''))
        token = os.environ.get('INVENTORY_EXPIRY_TOKEN', '')
        if len(token) < 32 or '\r' in token or '\n' in token:
            raise ValueError('invalid token')
        result = await asyncio.to_thread(send_expiry, url, token)
    except Exception:
        logger.error('Inventory expiry failed at %s', datetime.now(UTC).isoformat())
        raise RuntimeError('inventory expiry request failed') from None
    logger.info('Inventory expiry completed at %s: scanned=%d expired=%d skipped=%d has_more=%s',
        datetime.now(UTC).isoformat(), result['scanned'], result['expired'], result['skipped'], result['has_more'])
    return result
