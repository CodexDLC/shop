from django.db import models


class Product(models.Model):
    slug = models.SlugField(unique=True)
    brand = models.ForeignKey("catalog.Brand", on_delete=models.PROTECT, related_name="products")
    category = models.ForeignKey("catalog.Category", on_delete=models.PROTECT, related_name="products")
    model_name = models.CharField(max_length=160)
    manufacturer_article = models.CharField(max_length=100, blank=True)
    description_key = models.CharField(max_length=160, blank=True)
    tags = models.ManyToManyField("catalog.Tag", related_name="products", blank=True)
    is_active = models.BooleanField(default=True)
    new_until = models.DateField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return self.model_name
