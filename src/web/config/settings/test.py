import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-a-production-secret")
os.environ.setdefault("POSTGRES_PASSWORD", "test-only")
os.environ.setdefault("SHOP_MFA_ENCRYPTION_KEYS", "dGVzdC1vbmx5LW1mYS1rZXktMzItYnl0ZXMtbG9uZyE=")
from .base import *  # noqa: E402,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
ALLOWED_HOSTS = ["testserver", "localhost"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
SHOP_STAFF_MFA_REQUIRED = False  # Existing staff unit tests; identity integration tests explicitly enforce True.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
