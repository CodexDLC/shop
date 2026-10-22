import hashlib
import json

from django.core import signing
from django.db import IntegrityError, transaction
from django.db.models import F

from web.shop.identity import PUBLIC_FIELDS
from web.shop.models import StoreIdentity
from web.staff.audit import record_staff_action

STATE_SALT = "staff.store-identity.v1"


def identity_state(actor, identity):
    values = {field: getattr(identity, field) for field in PUBLIC_FIELDS} if identity else {}
    digest = hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    return {"actor": str(actor.pk), "exists": identity is not None,
            "revision": identity.revision if identity else 0, "fingerprint": digest}


def save_store_identity(request, values, token):
    """CAS rejects stale/actor-swapped forms, with audit in the same transaction."""
    try:
        submitted = signing.loads(token, salt=STATE_SALT, max_age=7200)
    except signing.BadSignature:
        return False
    with transaction.atomic():
        identity = StoreIdentity.objects.filter(pk=1).first()
        if submitted != identity_state(request.user, identity):
            return False
        cleaned = {field: values[field] for field in PUBLIC_FIELDS}
        if identity:
            previous = {field: getattr(identity, field) for field in PUBLIC_FIELDS}
            changed = StoreIdentity.objects.filter(pk=1, revision=identity.revision, **previous).update(
                **cleaned, revision=F("revision") + 1,
            )
            if not changed:
                return False
        else:
            try:
                with transaction.atomic():
                    identity = StoreIdentity.objects.create(pk=1, revision=1, **cleaned)
            except IntegrityError:
                return False
        record_staff_action(request, "store_identity.updated", identity)
    return True
