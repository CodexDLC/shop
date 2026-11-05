from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def stock_mode():
    mode = getattr(settings, 'SHOP_CHECKOUT_STOCK_MODE', 'demo')
    if mode not in ('demo', 'inventory_test'):
        raise ImproperlyConfigured('Invalid checkout stock mode.')
    return mode


def reservation_ttl():
    value = getattr(settings, 'SHOP_CHECKOUT_RESERVATION_TTL_SECONDS', 1800)
    if type(value) is not int or not 60 <= value <= 3600:
        raise ImproperlyConfigured('Invalid TEST checkout reservation TTL.')
    return value
