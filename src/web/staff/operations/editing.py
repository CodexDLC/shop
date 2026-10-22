import hashlib
import json

from django.core import signing


def fingerprint(obj):
    if obj is None:
        return "new"
    names = {
        "cart.promocode": ("code", "kind", "value", "min_subtotal", "currency", "is_active", "starts_at", "ends_at"),
        "support.contactticket": ("name", "email", "topic", "message", "resolved", "user_id", "created_at"),
    }[obj._meta.label_lower]
    content = {name: getattr(obj, name) for name in names}
    return hashlib.sha256(json.dumps(content, sort_keys=True, default=str).encode()).hexdigest()


def issue_state(label, obj=None):
    return signing.dumps({"pk": obj.pk if obj else None, "digest": fingerprint(obj)}, salt=f"staff.record.{label}")


def check_state(label, token, obj=None):
    try:
        state = signing.loads(token, salt=f"staff.record.{label}", max_age=3600)
    except (signing.BadSignature, TypeError, ValueError):
        return False
    return state == {"pk": obj.pk if obj else None, "digest": fingerprint(obj)}
