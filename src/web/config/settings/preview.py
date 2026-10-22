"""Loopback-only visual preview, using no external database or integrations."""

from .test import *  # noqa: F403

DEBUG = True
SEO_FORCE_NOINDEX = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
