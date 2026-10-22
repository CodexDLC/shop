from django.db import models


class ProductImage(models.Model):
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="images")
    # Empty means general fallback; sizes share the same colour gallery.
    color_code = models.CharField(max_length=40, blank=True)
    image_url = models.URLField(max_length=1000, blank=True)
    file = models.ImageField(upload_to="products/", blank=True, max_length=200)
    alt_key = models.CharField(max_length=160, blank=True)
    alt_text = models.CharField(max_length=300, blank=True)
    position = models.PositiveSmallIntegerField(default=0)

    @property
    def public_url(self):
        return self.file.url if self.file else self.image_url

    class Meta:
        ordering = ["position", "pk"]
        constraints = [models.UniqueConstraint(
            fields=["product", "color_code", "position"], name="catalog_unique_gallery_position"
        )]
