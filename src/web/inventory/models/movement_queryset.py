from django.core.exceptions import PermissionDenied
from django.db import models


class MovementQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionDenied('Inventory history is append-only.')

    def delete(self):
        raise PermissionDenied('Inventory history is append-only.')

    def bulk_update(self, *args, **kwargs):
        raise PermissionDenied('Inventory history is append-only.')

    def bulk_create(self, *args, **kwargs):
        raise PermissionDenied('Inventory history must be created by the inventory service.')
