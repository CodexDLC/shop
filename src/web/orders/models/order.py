import uuid

from django.db import models


class Order(models.Model):
    """An order record, not an implemented checkout or financial ledger."""

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=30, default="draft", choices=[
        ("draft", "order.status.draft"),
        ("awaiting_payment", "order.status.awaiting_payment"),
        ("confirmed", "order.status.confirmed"),
        ("cancelled", "order.status.cancelled"),
    ])
    currency = models.CharField(max_length=3, default="EUR")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=models.Q(total_amount__gte=0), name="order_total_nonnegative",
        )]
