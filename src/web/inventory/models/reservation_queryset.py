from django.core.exceptions import PermissionDenied
from django.db import models


class ReservationQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionDenied('Reservation mutations require the inventory service.')

    def delete(self):
        raise PermissionDenied('Reservation history cannot be deleted.')

    def bulk_update(self, *args, **kwargs):
        raise PermissionDenied('Reservation mutations require the inventory service.')

    def bulk_create(self, *args, **kwargs):
        raise PermissionDenied('Reservations must be created by the inventory service.')
