from django.conf import settings
from django.db import models


class CustomerAddress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="customer_addresses")
    kind = models.CharField(max_length=12, choices=[("standard", "Standard"), ("packstation", "Packstation")])
    recipient = models.CharField(max_length=150)
    street_address = models.CharField(max_length=200, blank=True)
    post_number = models.CharField(max_length=10, blank=True)
    station_number = models.CharField(max_length=5, blank=True)
    postal_code = models.CharField(max_length=5)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=2, choices=[("DE", "Deutschland")], default="DE")
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "pk"]
        constraints = [models.UniqueConstraint(fields=["user"], condition=models.Q(is_default=True),
                                               name="customer_one_default_address")]

    def __str__(self):
        return f"CustomerAddress #{self.pk} ({self.kind})"
