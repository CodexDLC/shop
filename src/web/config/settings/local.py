from .base import *  # noqa: F403

DEBUG = True
SEO_FORCE_NOINDEX = True
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
# Shared local Mailpit; no external SMTP delivery or credentials.
MAILERS = {"default": {
    "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
    "OPTIONS": {"host": "127.0.0.1", "port": 1025, "timeout": 10,
                "use_tls": False, "use_ssl": False},
}}
