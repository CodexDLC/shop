import hmac
import json
import logging
from dataclasses import asdict
from datetime import UTC, datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import RequestDataTooBig
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from web.inventory.expiry_service import expire_due_reservations

logger = logging.getLogger(__name__)
MAX_BODY = 8192


def _response(data, status):
    response = JsonResponse(data, status=status)
    response['Cache-Control'] = 'no-store'
    return response


@csrf_exempt  # This internal endpoint accepts only its dedicated bearer token, never session auth.
def expire_due(request):
    if not getattr(settings, 'INVENTORY_EXPIRY_ENABLED', False):
        return _response({'error': 'not_found'}, 404)
    if request.method != 'POST':
        response = _response({'error': 'method_not_allowed'}, 405)
        response['Allow'] = 'POST'
        return response
    token = getattr(settings, 'INVENTORY_EXPIRY_TOKEN', '')
    supplied = request.headers.get('Authorization', '')
    if (not isinstance(token, str) or len(token) < 32 or '\r' in token or '\n' in token
            or not hmac.compare_digest(supplied.encode('utf-8'), f'Bearer {token}'.encode('utf-8'))):
        return _response({'error': 'forbidden'}, 403)
    try:
        if int(request.META.get('CONTENT_LENGTH') or 0) > MAX_BODY:
            return _response({'error': 'body_too_large'}, 413)
        body = request.body
        if len(body) > MAX_BODY:
            return _response({'error': 'body_too_large'}, 413)
        if body and json.loads(body) != {}:
            return _response({'error': 'invalid_body'}, 400)
    except RequestDataTooBig:
        return _response({'error': 'body_too_large'}, 413)
    except (ValueError, UnicodeDecodeError):
        return _response({'error': 'invalid_body'}, 400)
    try:
        actor = get_user_model().objects.get(pk=getattr(settings, 'INVENTORY_EXPIRY_ACTOR_ID', None))
        result = expire_due_reservations(actor=actor, now=timezone.now(),
            batch_size=getattr(settings, 'INVENTORY_EXPIRY_BATCH_SIZE', 100))
        counts = asdict(result)
        logger.info('Inventory expiry completed at %s: scanned=%d expired=%d skipped=%d has_more=%s',
            datetime.now(UTC).isoformat(), counts['scanned'], counts['expired'], counts['skipped'],
            counts['has_more'])
        return _response(counts, 200)
    except Exception:
        logger.error('Inventory expiry failed at %s', datetime.now(UTC).isoformat())
        return _response({'error': 'unavailable'}, 503)
