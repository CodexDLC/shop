"""Isolated HTTPS staging behind the host's loopback-only Nginx proxy."""

import os

from .base import *  # noqa: F403

DEBUG = False
SEO_FORCE_NOINDEX = True
MIDDLEWARE = ["web.staging.noindex_middleware.NoIndexMiddleware", *MIDDLEWARE]  # noqa: F405
ALLOWED_HOSTS = ["shop.pinlite.dev"]
CSRF_TRUSTED_ORIGINS = ["https://shop.pinlite.dev"]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_NAME = "shop_staging_sessionid"
CSRF_COOKIE_NAME = "shop_staging_csrftoken"
SESSION_COOKIE_DOMAIN = None
CSRF_COOKIE_DOMAIN = None
STATIC_URL = "/static/"
MEDIA_URL = "/media/"
DEFAULT_FROM_EMAIL = "Männermasche Test <noreply@shop.pinlite.dev>"
SERVER_EMAIL = "errors@shop.pinlite.dev"
MAILERS = {"default": {
    "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
    "OPTIONS": {"host": "mailpit", "port": 1025, "timeout": 10,
                "use_tls": False, "use_ssl": False},
}}
EBAY_NOTIFICATION_ENDPOINT = "https://shop.pinlite.dev/integrations/ebay/account-deletion/"
EBAY_NOTIFICATION_VERIFICATION_TOKEN = os.environ.get("EBAY_NOTIFICATION_VERIFICATION_TOKEN", "")
# Seller OAuth tokens are encrypted in the shop database after explicit seller consent.
EBAY_APP_ID = os.environ.get("EBAY_APP_ID", "")
EBAY_CERT_ID = os.environ.get("EBAY_CERT_ID", "")
