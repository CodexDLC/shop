from django.core.exceptions import PermissionDenied

from web.inventory.access import require_actor

READ_PERMISSIONS = {'balance': 'view_stockbalance', 'history': 'view_inventorymovement',
    'reservations': 'view_reservationline'}


def can_read_inventory(user):
    return user.is_active and user.is_staff and any(user.has_perm('inventory.' + permission)
        for permission in READ_PERMISSIONS.values())


def selected_section(user, requested=None):
    if requested is not None:
        if requested not in READ_PERMISSIONS:
            raise PermissionDenied
        require_actor(user, READ_PERMISSIONS[requested])
        return requested
    for section, permission in READ_PERMISSIONS.items():
        try:
            require_actor(user, permission)
            return section
        except PermissionDenied:
            continue
    raise PermissionDenied
