from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied


def require_actor(actor, permission):
    user_model = get_user_model()
    if not isinstance(actor, user_model) or actor.pk is None:
        raise PermissionDenied
    trusted = user_model.objects.filter(pk=actor.pk, is_active=True, is_staff=True).first()
    if trusted is None or not trusted.has_perm(f'inventory.{permission}'):
        raise PermissionDenied
    return trusted
