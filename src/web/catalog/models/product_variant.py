from django.core.validators import RegexValidator
from django.db import models


class ProductVariant(models.Model):
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="variants")
    sku = models.CharField(max_length=100, unique=True)
    color_code = models.CharField(max_length=40)
    color_name_key = models.CharField(max_length=160)
    color_hex = models.CharField(max_length=7, default="#183F30", validators=[RegexValidator(r"^#[0-9a-fA-F]{6}$")])
    size = models.CharField(max_length=20)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="EUR", validators=[RegexValidator(r"^[A-Z]{3}$")])
    # Demonstration stock only. Reservations and real channel inventory are separate future features.
    demo_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(fields=["product", "color_code", "size"], name="catalog_unique_variant"),
            models.CheckConstraint(condition=models.Q(price__gte=0), name="catalog_nonnegative_price"),
            models.CheckConstraint(condition=models.Q(demo_quantity__gte=0), name="catalog_nonnegative_demo_qty"),
        ]

    @property
    def is_available(self):
        return self.is_active and self.demo_quantity > 0

    def __str__(self):
        return self.sku
