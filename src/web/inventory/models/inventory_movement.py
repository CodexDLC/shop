from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connection, models, transaction

from codex_ecommerce.inventory import InventoryInvariantError
from web.inventory.write_access import require_service_write

from .movement_queryset import MovementQuerySet


class InventoryMovement(models.Model):
    variant = models.ForeignKey('catalog.ProductVariant', on_delete=models.PROTECT, related_name='inventory_movements')
    location_id = models.CharField(max_length=40)
    kind = models.CharField(max_length=20)
    source = models.CharField(max_length=40)
    owner = models.CharField(max_length=80)
    operation_key = models.CharField(max_length=160)
    fingerprint = models.CharField(max_length=64)
    quantity = models.BigIntegerField()
    expected_revision = models.BigIntegerField()
    reason = models.CharField(max_length=500)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    before_on_hand = models.BigIntegerField()
    before_reserved = models.BigIntegerField()
    after_on_hand = models.BigIntegerField()
    after_reserved = models.BigIntegerField()
    delta_on_hand = models.BigIntegerField()
    delta_reserved = models.BigIntegerField()
    revision = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    reservation = models.ForeignKey('inventory.ReservationLine', null=True, on_delete=models.PROTECT,
        related_name='movements')
    expected_reservation_revision = models.BigIntegerField(null=True)
    before_reservation = models.JSONField(null=True)
    after_reservation = models.JSONField(null=True)
    decision_at = models.DateTimeField(null=True)
    received = models.BooleanField(null=True)
    inspected = models.BooleanField(null=True)

    objects = MovementQuerySet.as_manager()

    class Meta:
        base_manager_name = 'objects'
        default_permissions = ('view',)
        ordering = ['-pk']
        indexes = [models.Index(fields=['variant', 'location_id', '-id'], name='inventory_history_target')]
        constraints = [
            models.UniqueConstraint(fields=['source', 'owner', 'operation_key'], name='inventory_unique_operation'),
            models.CheckConstraint(condition=models.Q(location_id='main'), name='inventory_movement_main'),
            models.CheckConstraint(condition=models.Q(kind__in=[
                'initialize', 'receive', 'adjust', 'reserve', 'commit', 'release', 'fulfill', 'expire',
                'checked_return', 'external_snapshot',
            ]), name='inventory_accounting_kind'),
            models.CheckConstraint(condition=(
                models.Q(kind__in=['initialize', 'receive', 'adjust', 'external_snapshot'], reservation__isnull=True,
                    expected_reservation_revision__isnull=True, before_reservation__isnull=True,
                    after_reservation__isnull=True, decision_at__isnull=True)
                | models.Q(kind='reserve', reservation__isnull=False, expected_reservation_revision=0,
                    expected_reservation_revision__isnull=False,
                    before_reservation__isnull=True, after_reservation__isnull=False, decision_at__isnull=False)
                | models.Q(kind__in=['commit', 'release', 'fulfill', 'expire', 'checked_return'], reservation__isnull=False,
                    expected_reservation_revision__gte=1, expected_reservation_revision__isnull=False,
                    before_reservation__isnull=False, after_reservation__isnull=False, decision_at__isnull=False)
            ), name='inventory_movement_reservation'),
            models.CheckConstraint(condition=(
                models.Q(kind='checked_return', received=True, inspected=True,
                    received__isnull=False, inspected__isnull=False)
                | (~models.Q(kind='checked_return') & models.Q(received__isnull=True, inspected__isnull=True))
            ), name='inventory_return_attestations'),
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name='inventory_movement_quantity'),
            models.CheckConstraint(condition=models.Q(expected_revision__gte=0), name='inventory_expected_revision'),
            models.CheckConstraint(condition=models.Q(before_reserved__gte=0, after_reserved__gte=0), name='inventory_movement_reserved'),
            models.CheckConstraint(condition=models.Q(before_on_hand__gte=models.F('before_reserved'), after_on_hand__gte=models.F('after_reserved')), name='inventory_movement_stock'),
            models.CheckConstraint(condition=models.Q(revision__gte=1), name='inventory_movement_revision'),
            models.CheckConstraint(condition=models.Q(delta_on_hand=models.F('after_on_hand') - models.F('before_on_hand'), delta_reserved=models.F('after_reserved') - models.F('before_reserved')), name='inventory_movement_deltas'),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionDenied('Inventory history is append-only.')
        require_service_write()
        if not connection.in_atomic_block:
            raise InventoryInvariantError()
        from .inventory_change_event import InventoryChangeEvent

        # The enclosing service owns balance/line/audit/order atomicity. This
        # savepoint also prevents a trusted caller catching an event failure
        # from leaving an orphan movement in its outer transaction.
        with transaction.atomic():
            result = super().save(*args, **kwargs)
            InventoryChangeEvent.objects.create(movement=self, variant_id=self.variant_id,
                location_id=self.location_id, revision=self.revision, on_hand=self.after_on_hand,
                reserved=self.after_reserved, occurred_at=self.created_at)
            return result

    def delete(self, *args, **kwargs):
        raise PermissionDenied('Inventory history is append-only.')
