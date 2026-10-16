import uuid

from django.db import models


class RefundAttempt(models.Model):
    """No refund execution yet; future service must lock and check refundable balance."""

    operation_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    payment = models.ForeignKey("payments.PaymentAttempt", related_name="refund_attempts", on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, default="requested", choices=[
        ("requested", "refund.status.requested"), ("pending", "refund.status.pending"),
        ("succeeded", "refund.status.succeeded"), ("failed", "refund.status.failed"),
        ("unknown", "refund.status.unknown"),
    ])
    provider_reference = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name="refund_amount_positive")]
