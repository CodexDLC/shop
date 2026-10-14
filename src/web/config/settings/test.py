import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-a-production-secret")
os.environ.setdefault("POSTGRES_PASSWORD", "test-only")
from .base import *  # noqa: E402,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
ALLOWED_HOSTS = ["testserver", "localhost"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
