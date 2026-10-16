import time

from allauth.account.authentication import get_authentication_records
from allauth.account.models import EmailAddress
from allauth.mfa.models import Authenticator
from django.conf import settings


def is_staff_user(user):
    return user.is_authenticated and user.is_active and (user.is_staff or user.is_superuser)


def has_verified_email(user):
    return bool(user.email and EmailAddress.objects.filter(
        user=user, email__iexact=user.email, verified=True,
    ).exists())


def has_recent_mfa(request):
    """Only server-side proof tied to a currently enrolled device of this user."""
    authenticators = dict(Authenticator.objects.filter(user=request.user).values_list("pk", "type"))
    if Authenticator.Type.TOTP not in authenticators.values():
        return False
    now = time.time()
    for record in get_authentication_records(request):
        if not isinstance(record, dict) or record.get("method") != "mfa":
            continue
        at = record.get("at")
        auth_type = authenticators.get(record.get("id"))
        if (auth_type in (Authenticator.Type.TOTP, Authenticator.Type.RECOVERY_CODES)
                and auth_type == record.get("type") and isinstance(at, (float, int))
                and 0 <= now - at <= settings.SHOP_STAFF_MFA_MAX_AGE):
            return True
    return False
