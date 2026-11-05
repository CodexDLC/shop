"""Isolated PostgreSQL test target; never fall back to the working database."""
import os
import re

from django.core.exceptions import ImproperlyConfigured

from .test import *  # noqa: F403

_name = os.environ.get("INVENTORY_TEST_DB_NAME", "")
_host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
if (os.environ.get("INVENTORY_POSTGRES_TESTS") != "1"
        or not re.fullmatch(r"test_inet_inventory_[0-9a-f]{32}", _name)
        or _host not in {"127.0.0.1", "localhost", "::1"}
        or _name == os.environ.get("POSTGRES_DB")):
    raise ImproperlyConfigured("Use tools/test_inventory_postgres.py for an isolated local test database.")

DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    # NAME is also the isolated name: an accidental non-test command cannot address the working database.
    "NAME": _name,
    "USER": os.environ.get("POSTGRES_USER", "inet_mag"),
    "PASSWORD": os.environ["POSTGRES_PASSWORD"],
    "HOST": _host,
    "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    "CONN_MAX_AGE": 0,
    "TEST": {"NAME": _name},
    "OPTIONS": {"options": "-c lock_timeout=5000 -c statement_timeout=30000"},
}}
