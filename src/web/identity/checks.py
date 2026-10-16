from cryptography.fernet import Fernet
from django.conf import settings
from django.core.checks import Error, register


@register()
def mfa_configuration(app_configs, **kwargs):
    try:
        if not settings.SHOP_MFA_ENCRYPTION_KEYS:
            raise ValueError
        for key in settings.SHOP_MFA_ENCRYPTION_KEYS:
            Fernet(key.encode("ascii"))
    except (ValueError, UnicodeError):
        return [Error("Configure dedicated SHOP_MFA_ENCRYPTION_KEYS before enabling authentication.", id="shop_auth.E001")]
    return []
