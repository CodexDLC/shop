import hashlib
import json
import secrets

from django.core import signing


def session_owner(request):
    value = request.session.get("local_commerce_owner")
    if value is None:
        value = secrets.token_hex(32)
        request.session["local_commerce_owner"] = value
    principal = str(request.user.pk) if request.user.is_authenticated else "guest"
    return hashlib.sha256(f"{value}:{principal}".encode()).hexdigest()


def address_key(request):
    principal = str(request.user.pk) if request.user.is_authenticated else "guest"
    return f"local_checkout_address_{principal}"


def checkout_fingerprint(cart, address):
    payload = {"address": address, "lines": [
        {key: line[key] for key in ("sku", "quantity", "unit_amount", "name", "brand", "colour_name", "size")}
        for line in cart["lines"]
    ], "shipping": cart["shipping_amount"], "currency": cart["currency"],
        "subtotal": cart['subtotal'], "discount": cart['discount_amount'], "total": cart['total'],
        "coupon_code": cart['coupon_code'], "coupon_signature": cart['coupon_signature']}
    return hashlib.sha256(json.dumps(payload, default=str, sort_keys=True).encode()).hexdigest()


def review_token(request, cart, address):
    nonce_key = address_key(request) + "_nonce"
    nonce = request.session.get(nonce_key)
    if nonce is None:
        return ""
    return signing.dumps({"owner": session_owner(request), "fingerprint": checkout_fingerprint(cart, address),
                          "nonce": nonce},
                         salt="local-test-checkout")


def read_token(request, token):
    payload = signing.loads(token, salt="local-test-checkout", max_age=3600)
    if payload["owner"] != session_owner(request):
        raise signing.BadSignature("Wrong checkout owner")
    return payload


def token_key(payload):
    # Timestamp signatures can differ across review refreshes; one checkout intent
    # still has exactly one durable operation identity.
    return hashlib.sha256(f"{payload['owner']}:{payload['nonce']}".encode()).hexdigest()
