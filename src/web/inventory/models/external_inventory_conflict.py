from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models

from web.inventory.write_access import require_service_write

from .movement_queryset import MovementQuerySet


class ExternalInventoryConflict(models.Model):
    receipt = models.ForeignKey('inventory.ExternalInventoryReceipt', on_delete=models.PROTECT)
    attempted_fingerprint = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    observed_at = models.DateTimeField()

    objects = MovementQuerySet.as_manager()

    class Meta:
        base_manager_name = 'objects'
        default_permissions = ('view',)
        ordering = ['pk']
        constraints = [models.UniqueConstraint(fields=['receipt', 'attempted_fingerprint'],
            name='inventory_fake_unique_conflict')]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionDenied('Synthetic source conflicts are append-only.')
        require_service_write()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied('Synthetic source conflicts are append-only.')
