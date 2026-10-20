import base64
import hashlib
import http.client
import json
import re
import ssl
from urllib.parse import urlencode

from django.conf import settings
from django.core.cache import cache

from .rejected import NotificationRejected


class PublicKeyClient:
    """Fixed-origin, bounded eBay authentication/public-key reads; no selling API."""

    def _request(self, method, path, headers, body=None):
        allowed = (
            method == "POST" and path == "/identity/v1/oauth2/token"
        ) or (
            method == "GET"
            and isinstance(path, str)
            and re.fullmatch(r"/commerce/notification/v1/public_key/[A-Za-z0-9_-]{1,200}", path)
        )
        if not allowed:
            raise NotificationRejected("ebay.read_only_violation", 503)
        connection = http.client.HTTPSConnection(
            "api.ebay.com", timeout=5, context=ssl.create_default_context()
        )
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            content = response.read(32769)
            if response.status != 200 or len(content) > 32768:
                raise NotificationRejected("ebay.verification_unavailable", 503)
            result = json.loads(content)
            if not isinstance(result, dict):
                raise ValueError
            return result
        except NotificationRejected:
            raise
        except (OSError, http.client.HTTPException, ValueError, UnicodeError):
            raise NotificationRejected("ebay.verification_unavailable", 503) from None
        finally:
            connection.close()

    def get(self, kid):
        if not isinstance(kid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", kid):
            raise NotificationRejected("ebay.invalid_signature")
        app_id = getattr(settings, "EBAY_APP_ID", "")
        secret = getattr(settings, "EBAY_CERT_ID", "")
        if not app_id or not secret:
            raise NotificationRejected("ebay.configuration_unavailable", 503)
        namespace = hashlib.sha256(app_id.encode()).hexdigest()[:24]
        key_cache = f"ebay-notification:{namespace}:key:{kid}"
        token_cache = f"ebay-notification:{namespace}:token"
        try:
            public_key = cache.get(key_cache)
            if public_key:
                return public_key
            token = cache.get(token_cache)
            if not token:
                credentials = base64.b64encode(f"{app_id}:{secret}".encode()).decode("ascii")
                auth = self._request(
                    "POST", "/identity/v1/oauth2/token",
                    {"Authorization": f"Basic {credentials}",
                     "Content-Type": "application/x-www-form-urlencoded"},
                    urlencode({"grant_type": "client_credentials",
                               "scope": "https://api.ebay.com/oauth/api_scope"}),
                )
                token = auth.get("access_token")
                expiry = auth.get("expires_in")
                if not isinstance(token, str) or not token or not isinstance(expiry, int) or expiry <= 60:
                    raise NotificationRejected("ebay.verification_unavailable", 503)
                cache.set(token_cache, token, min(expiry - 60, 3600))
            public_key = self._request(
                "GET", f"/commerce/notification/v1/public_key/{kid}",
                {"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
            if not isinstance(public_key.get("key"), str):
                raise NotificationRejected("ebay.verification_unavailable", 503)
            cache.set(key_cache, public_key, 3600)
            return public_key
        except NotificationRejected:
            raise
        except Exception:
            # Cache/backend failures must not acknowledge an unverified notification.
            raise NotificationRejected("ebay.verification_unavailable", 503) from None
