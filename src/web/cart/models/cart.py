from django.db import models


class Cart(models.Model):
    """Persistence seam only; checkout/reservation operations are not implemented."""

    currency = models.CharField(max_length=3, default="EUR")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
