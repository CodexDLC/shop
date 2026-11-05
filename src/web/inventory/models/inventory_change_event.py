import uuid

from django.core.exceptions import PermissionDenied
from django.db import models

from codex_ecommerce.inventory import InventoryChanged, StockKey, StockSnapshot
from web.inventory.write_access import require_service_write

from .movement_queryset import MovementQuerySet


class InventoryChangeEvent(models.Model):
    """Append-only movement-linked journal. No delivery state or dispatcher."""

    event_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    movement = models.OneToOneField('inventory.InventoryMovement', on_delete=models.PROTECT,
        related_name='change_event')
    version = models.PositiveSmallIntegerField(default=1)
    variant = models.ForeignKey('catalog.ProductVariant', on_delete=models.PROTECT)
    location_id = models.CharField(max_length=40)
    revision = models.BigIntegerField()
    on_hand = models.BigIntegerField()
    reserved = models.BigIntegerField()
    occurred_at = models.DateTimeField()

    objects = MovementQuerySet.as_manager()

    class Meta:
        base_manager_name = 'objects'
        default_permissions = ('view',)
        ordering = ['pk']
        constraints = [
            models.UniqueConstraint(fields=['variant', 'location_id', 'revision'], name='inventory_event_revision'),
            models.CheckConstraint(condition=models.Q(version=1, location_id='main', revision__gte=1,
                reserved__gte=0, on_hand__gte=models.F('reserved')), name='inventory_event_snapshot'),
        ]

    def snapshot(self):
        return InventoryChanged(str(self.event_id), self.version, self.movement_id,
            StockSnapshot(StockKey(str(self.variant_id), self.location_id), self.on_hand, self.reserved, self.revision),
            self.occurred_at, self.pk)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionDenied('Inventory events are append-only.')
        require_service_write()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied('Inventory events are append-only.')
