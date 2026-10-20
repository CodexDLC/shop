import uuid

from django.conf import settings
from django.db import models


class Order(models.Model):
    """An order record, not an implemented checkout or financial ledger."""

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=30, default="draft", choices=[
        ("draft", "order.status.draft"),
        ("awaiting_payment", "order.status.awaiting_payment"),
        ("confirmed", "order.status.confirmed"),
        ("cancelled", "order.status.cancelled"),
        ("test_created", "commerce.order.status.created"),
    ])
    currency = models.CharField(max_length=3, default="EUR")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="local_test_orders")
    session_owner = models.CharField(max_length=64, blank=True)
    checkout_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    address = models.JSONField(default=dict, blank=True)
    is_test = models.BooleanField(default=True)
    shipping_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=models.Q(total_amount__gte=0), name="order_total_nonnegative",
        )]
