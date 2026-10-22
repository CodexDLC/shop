from django.db import models


class StoreIdentity(models.Model):
    """Public seller identity only; unrelated to payment, tax or SMTP configuration."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    legal_name = models.CharField(max_length=200)
    representative = models.CharField(max_length=200, blank=True)
    street_address = models.CharField(max_length=200)
    postal_code = models.CharField(max_length=20)
    city = models.CharField(max_length=120)
    country = models.CharField(max_length=2, default="DE")
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=60, blank=True)
    vat_id = models.CharField(max_length=60, blank=True)
    register_court = models.CharField(max_length=200, blank=True)
    register_number = models.CharField(max_length=100, blank=True)
    revision = models.PositiveBigIntegerField(default=0, editable=False)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="shop_single_store_identity")]
