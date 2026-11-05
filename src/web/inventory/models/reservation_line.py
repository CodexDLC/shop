from django.core.exceptions import PermissionDenied
from django.db import models

from web.inventory.write_access import require_service_write

from .reservation_queryset import ReservationQuerySet


class ReservationLine(models.Model):
    """Opaque future order-line reference; no existing order binding is implied."""

    reference = models.CharField(max_length=100, primary_key=True)
    variant = models.ForeignKey('catalog.ProductVariant', on_delete=models.PROTECT, related_name='inventory_reservations')
    location_id = models.CharField(max_length=40, default='main')
    original = models.BigIntegerField()
    remaining_reserved = models.BigIntegerField()
    consumed = models.BigIntegerField(default=0)
    released = models.BigIntegerField(default=0)
    returned = models.BigIntegerField(default=0)
    state = models.CharField(max_length=12)
    expires_at = models.DateTimeField(null=True)
    revision = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    order_line = models.OneToOneField('orders.OrderLine', null=True, blank=True, on_delete=models.PROTECT,
        related_name='inventory_reservation')

    objects = ReservationQuerySet.as_manager()

    class Meta:
        base_manager_name = 'objects'
        default_permissions = ('view',)
        permissions = [
            ('reserve_reservationline', 'Can reserve stock'),
            ('commit_reservationline', 'Can commit reservations'),
            ('release_reservationline', 'Can release reservations'),
            ('fulfill_reservationline', 'Can fulfill reservations'),
            ('expire_reservationline', 'Can expire due reservations'),
            ('checked_return_reservationline', 'Can accept received and inspected returns'),
        ]
        ordering = ['reference']
        indexes = [
            models.Index(fields=['variant', 'location_id', 'reference'], name='inventory_reservation_target'),
            models.Index(fields=['state', 'expires_at', 'variant', 'reference'], name='inventory_due_reservations'),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(returned__gte=0, returned__lte=models.F('consumed')),
                name='inventory_returned_consumed'),
            models.CheckConstraint(condition=models.Q(location_id='main'), name='inventory_reservation_main'),
            models.CheckConstraint(condition=models.Q(original__gt=0, remaining_reserved__gte=0,
                consumed__gte=0, released__gte=0, revision__gte=1), name='inventory_reservation_counters'),
            models.CheckConstraint(condition=models.Q(original=models.F('remaining_reserved')
                + models.F('consumed') + models.F('released')), name='inventory_reservation_conservation'),
            models.CheckConstraint(condition=(
                models.Q(state='held', remaining_reserved__gt=0, consumed=0, expires_at__isnull=False)
                | models.Q(state='committed', remaining_reserved__gt=0, expires_at__isnull=True)
                | models.Q(state='closed', remaining_reserved=0, expires_at__isnull=True)
            ), name='inventory_reservation_state'),
        ]

    @classmethod
    def from_db(cls, db, field_names, values, *, fetch_mode=None):
        instance = super().from_db(db, field_names, values, fetch_mode=fetch_mode)
        instance._inventory_reference = instance.pk
        return instance

    def save(self, *args, **kwargs):
        require_service_write()
        if self._state.adding:
            if kwargs.get('force_update'):
                raise PermissionDenied('New reservations cannot replace an existing reference.')
            kwargs['force_insert'] = True
        else:
            original_reference = getattr(self, '_inventory_reference', self.pk)
            identity = (self.reference, self.variant_id, self.location_id, self.original, self.order_line_id)
            original = type(self).objects.filter(pk=original_reference).values_list(
                'reference', 'variant_id', 'location_id', 'original', 'order_line_id').first()
            if original != identity:
                raise PermissionDenied('Reservation identity is immutable.')
        result = super().save(*args, **kwargs)
        self._inventory_reference = self.pk
        return result

    def delete(self, *args, **kwargs):
        raise PermissionDenied('Reservation history cannot be deleted.')
