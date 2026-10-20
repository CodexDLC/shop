from urllib.parse import urlsplit

from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings

from .rejected import OAuthRejected

SCOPES = (
    "https://api.ebay.com/oauth/api_scope",
    "https://api.ebay.com/oauth/api_scope/sell.inventory.readonly",
    "https://api.ebay.com/oauth/api_scope/sell.listing.read",
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment.readonly",
    "https://api.ebay.com/oauth/api_scope/commerce.notification.subscription",
)
COOKIE = "__Host-shop_ebay_oauth"
PREFIX = "/integrations/ebay/oauth/"


def configuration():
    base = getattr(settings, "EBAY_OAUTH_BASE_URL", "").rstrip("/")
    parsed = urlsplit(base)
    runame = getattr(settings, "EBAY_OAUTH_RUNAME", "")
    keys = getattr(settings, "EBAY_OAUTH_ENCRYPTION_KEYS", [])
    if isinstance(keys, str):
        keys = [key.strip() for key in keys.split(",") if key.strip()]
    try:
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.path or parsed.query or parsed.fragment or not runame or len(runame) > 256
                or not settings.EBAY_APP_ID or not settings.EBAY_CERT_ID or not keys):
            raise ValueError
        cipher = MultiFernet([Fernet(key) for key in keys])
    except (ValueError, TypeError, AttributeError):
        raise OAuthRejected from None
    return base, runame, cipher
