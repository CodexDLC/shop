from uuid import uuid4

from django.core import signing
from django.core.exceptions import ValidationError

from web.localization import translate_text

SALT = 'staff.inventory.intent.v1'
MAX_INT = 2**63 - 1


def issue_intent(actor, variant_id, action, revision):
    return signing.dumps({'actor': str(actor.pk), 'variant': variant_id, 'action': action,
        'revision': revision, 'key': uuid4().hex}, salt=SALT)


def read_intent(token, actor, variant_id, action):
    try:
        value = signing.loads(token, salt=SALT)
        if (not isinstance(value, dict) or value.get('actor') != str(actor.pk)
                or value.get('variant') != variant_id or value.get('action') != action
                or type(value.get('revision')) is not int or not 0 <= value['revision'] <= MAX_INT
                or not isinstance(value.get('key'), str) or len(value['key']) != 32):
            raise ValueError
        return value
    except (signing.BadSignature, ValueError, TypeError):
        raise ValidationError(translate_text('staff.inventory.error.intent')) from None
