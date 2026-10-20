import base64
import binascii
import json
import re

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from .public_key_client import PublicKeyClient
from .rejected import NotificationRejected


class SignatureVerifier:
    """eBay's ECC notification protocol, not JWS or HTTP Message Signatures."""

    def verify(self, body, header):
        try:
            if not isinstance(header, str) or not 1 <= len(header) <= 8192:
                raise ValueError
            envelope = json.loads(base64.b64decode(header, validate=True))
            if not isinstance(envelope, dict):
                raise ValueError
            # Official Node SDK uses ssl3-sha1; do not confuse challenge SHA-256 with this digest.
            if envelope.get("alg") not in ("ecdsa", "ECDSA") or envelope.get("digest") != "SHA1":
                raise ValueError
            kid = envelope.get("kid")
            if not isinstance(kid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", kid):
                raise ValueError
            signature = base64.b64decode(envelope["signature"], validate=True)
            if not 8 <= len(signature) <= 256:
                raise ValueError
        except (ValueError, TypeError, KeyError, binascii.Error, UnicodeError, RecursionError):
            raise NotificationRejected("ebay.invalid_signature") from None

        public = PublicKeyClient().get(kid)
        if public.get("algorithm") != "ECDSA" or public.get("digest") != "SHA1":
            raise NotificationRejected("ebay.unsupported_key")
        try:
            # eBay API/official SDK fixture may omit newlines around the PEM base64.
            pem = public["key"].strip()
            start, end = "-----BEGIN PUBLIC KEY-----", "-----END PUBLIC KEY-----"
            if not pem.startswith(start) or not pem.endswith(end):
                raise ValueError
            encoded = "".join(pem[len(start):-len(end)].split())
            pem = f"{start}\n{encoded}\n{end}\n"
            key = serialization.load_pem_public_key(pem.encode("ascii"))
            if not isinstance(key, ec.EllipticCurvePublicKey):
                raise ValueError
            key.verify(signature, body, ec.ECDSA(hashes.SHA1()))
        except (ValueError, TypeError, KeyError, UnicodeError, UnsupportedAlgorithm):
            raise NotificationRejected("ebay.verification_unavailable", 503) from None
        except InvalidSignature:
            raise NotificationRejected("ebay.invalid_signature") from None
