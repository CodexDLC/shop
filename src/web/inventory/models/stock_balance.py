from django.db import models

from web.inventory.write_access import require_service_write

from .balance_queryset import BalanceQuerySet


class StockBalance(models.Model):
    variant = models.ForeignKey('catalog.ProductVariant', on_delete=models.PROTECT, related_name='stock_balances')
    location_id = models.CharField(max_length=40, default='main')
    on_hand = models.BigIntegerField()
    reserved = models.BigIntegerField(default=0)
    revision = models.BigIntegerField()

    objects = BalanceQuerySet.as_manager()

    class Meta:
        base_manager_name = 'objects'
        default_permissions = ('view',)
        permissions = [
            ('initialize_stockbalance', 'Can initialize stock balance'),
            ('receive_stockbalance', 'Can receive stock'),
            ('adjust_stockbalance', 'Can adjust stock balance'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['variant', 'location_id'], name='inventory_unique_balance'),
            models.CheckConstraint(condition=models.Q(location_id='main'), name='inventory_main_location'),
            models.CheckConstraint(condition=models.Q(reserved__gte=0), name='inventory_reserved_nonnegative'),
            models.CheckConstraint(condition=models.Q(on_hand__gte=models.F('reserved')), name='inventory_stock_covers_reserved'),
            models.CheckConstraint(condition=models.Q(revision__gte=1), name='inventory_revision_positive'),
        ]

    def save(self, *args, **kwargs):
        require_service_write()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        require_service_write()
        return super().delete(*args, **kwargs)
