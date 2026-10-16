from django.db import models


class OrderLine(models.Model):
    """Purchase-time snapshot remains usable after catalogue edits/removal."""

    order = models.ForeignKey("orders.Order", related_name="lines", on_delete=models.PROTECT)
    sku = models.CharField(max_length=100)
    product_name = models.CharField(max_length=255)
    colour_name = models.CharField(max_length=100, blank=True)
    size_name = models.CharField(max_length=40, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="order_quantity_positive"),
            models.CheckConstraint(condition=models.Q(unit_amount__gte=0), name="order_unit_nonnegative"),
        ]
