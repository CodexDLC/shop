from django.db import models


class Product(models.Model):
    slug = models.SlugField(unique=True)
    brand = models.ForeignKey("catalog.Brand", on_delete=models.PROTECT, related_name="products")
    category = models.ForeignKey("catalog.Category", on_delete=models.PROTECT, related_name="products")
    model_name = models.CharField(max_length=160)
    manufacturer_article = models.CharField(max_length=100, blank=True)
    description_key = models.CharField(max_length=160, blank=True)
    tags = models.ManyToManyField("catalog.Tag", related_name="products", blank=True)
    materials = models.ManyToManyField("catalog.Material", related_name="products", blank=True)
    properties = models.ManyToManyField("catalog.ProductProperty", related_name="products", blank=True)
    is_active = models.BooleanField(default=True)
    new_until = models.DateField(null=True, blank=True, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    editorial_state = models.CharField(max_length=12, default="published", choices=[
        ("draft", "Draft"), ("review", "Review"), ("published", "Published"),
    ])
    review_fingerprint = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["pk"]
        permissions = [("publish_product", "Can publish and withdraw products")]

    @property
    def publication_state(self):
        if self.is_active:
            return "published"
        return "review" if self.editorial_state == "review" else "draft"

    def __str__(self):
        return self.model_name
