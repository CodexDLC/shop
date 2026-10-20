import re
from urllib.parse import urlsplit

from django.conf import settings

from .rejected import NotificationRejected


def challenge_configuration():
    token = getattr(settings, "EBAY_NOTIFICATION_VERIFICATION_TOKEN", "")
    endpoint = getattr(settings, "EBAY_NOTIFICATION_ENDPOINT", "")
    try:
        parsed = urlsplit(endpoint)
    except (ValueError, TypeError):
        raise NotificationRejected("ebay.configuration_unavailable", 503) from None
    if (
        not isinstance(token, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{32,80}", token)
        or parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise NotificationRejected("ebay.configuration_unavailable", 503)
    return token, endpoint
