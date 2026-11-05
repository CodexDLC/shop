from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models

from codex_ecommerce.inventory import StockKey, StockSnapshot
from web.inventory.fake_source_result import FakeSourceResult
from web.inventory.write_access import require_service_write

from .movement_queryset import MovementQuerySet


class ExternalInventoryReceipt(models.Model):
    """Durable synthetic decisions; immutable retries retain their initial result."""

    external_id = models.CharField(max_length=100)
    variant = models.ForeignKey('catalog.ProductVariant', on_delete=models.PROTECT)
    kind = models.CharField(max_length=20)
    quantity = models.BigIntegerField()
    source_revision = models.BigIntegerField()
    expected_stock_revision = models.BigIntegerField(null=True)
    fingerprint = models.CharField(max_length=64)
    status = models.CharField(max_length=20)
    code = models.CharField(max_length=40)
    result_on_hand = models.BigIntegerField(null=True)
    result_reserved = models.BigIntegerField(null=True)
    result_revision = models.BigIntegerField(null=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    observed_at = models.DateTimeField()
    reservation = models.OneToOneField('inventory.ReservationLine', null=True, on_delete=models.PROTECT)

    objects = MovementQuerySet.as_manager()

    class Meta:
        base_manager_name = 'objects'
        default_permissions = ('view',)
        permissions = [('ingest_fake_inventory', 'Can ingest synthetic inventory test facts')]
        ordering = ['pk']
        indexes = [models.Index(fields=['variant', '-source_revision'], name='inventory_fake_source_version')]
        constraints = [
            models.UniqueConstraint(fields=['external_id'], name='inventory_fake_external_id'),
            models.CheckConstraint(condition=(models.Q(kind='snapshot', quantity__gte=0,
                expected_stock_revision__gte=1, expected_stock_revision__isnull=False)
                | models.Q(kind='completed_sale', quantity__gt=0, expected_stock_revision__isnull=True)),
                name='inventory_fake_fact_kind'),
            models.CheckConstraint(condition=models.Q(source_revision__gte=1,
                status__in=['applied', 'stale_snapshot', 'needs_attention']), name='inventory_fake_outcome'),
            models.CheckConstraint(condition=(models.Q(result_on_hand__isnull=True,
                result_reserved__isnull=True, result_revision__isnull=True)
                | models.Q(result_on_hand__isnull=False, result_reserved__isnull=False,
                    result_revision__isnull=False, result_reserved__gte=0, result_revision__gte=1,
                    result_on_hand__gte=models.F('result_reserved'))), name='inventory_fake_snapshot'),
        ]

    def snapshot(self):
        stock = None if self.result_on_hand is None else StockSnapshot(StockKey(str(self.variant_id), 'main'),
            self.result_on_hand, self.result_reserved, self.result_revision)
        return FakeSourceResult(self.pk, self.external_id, self.status, self.code, stock, self.reservation_id)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionDenied('Synthetic source receipts are append-only.')
        require_service_write()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied('Synthetic source receipts are append-only.')
