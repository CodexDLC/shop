from django.core.validators import MaxLengthValidator
from django.db import models


class ProductInformation(models.Model):
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="information")
    language_code = models.CharField(max_length=10, default="de")
    description = models.TextField(blank=True, validators=[MaxLengthValidator(6000)])
    composition = models.TextField(blank=True, validators=[MaxLengthValidator(2000)])
    care = models.TextField(blank=True, validators=[MaxLengthValidator(2000)])
    fit = models.TextField(blank=True, validators=[MaxLengthValidator(2000)])
    origin = models.CharField(max_length=500, blank=True)
    certification = models.CharField(max_length=1000, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["product", "language_code"], name="catalog_unique_product_information_language",
        )]

    def __str__(self):
        return f"{self.product} ({self.language_code})"
