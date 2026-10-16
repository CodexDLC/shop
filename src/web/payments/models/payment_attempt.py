import uuid

from django.db import models


class PaymentAttempt(models.Model):
    """Operation identity skeleton; no provider request or payment confirmation."""

    operation_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    order = models.ForeignKey("orders.Order", related_name="payment_attempts", on_delete=models.PROTECT)
    provider = models.CharField(max_length=20, default="stripe", choices=[("stripe", "Stripe")])
    method = models.CharField(max_length=20, choices=[("card", "payment.method.card"), ("paypal", "PayPal")])
    mode = models.CharField(max_length=20, default="demo", choices=[
        ("demo", "payment.mode.demo"), ("sandbox", "payment.mode.sandbox"),
    ])
    status = models.CharField(max_length=20, default="created", choices=[
        ("created", "payment.status.created"), ("pending", "payment.status.pending"),
        ("succeeded", "payment.status.succeeded"), ("failed", "payment.status.failed"),
        ("unknown", "payment.status.unknown"),
    ])
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="EUR")
    provider_reference = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gte=0), name="payment_amount_nonnegative"),
            models.CheckConstraint(condition=models.Q(provider="stripe"), name="payment_provider_stripe"),
            models.CheckConstraint(condition=models.Q(mode__in=["demo", "sandbox"]), name="payment_no_live"),
        ]
