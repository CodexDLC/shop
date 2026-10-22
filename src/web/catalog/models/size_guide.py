from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator
from django.db import models


class SizeGuide(models.Model):
    brand = models.ForeignKey("catalog.Brand", on_delete=models.CASCADE, related_name="size_guides")
    category = models.ForeignKey(
        "catalog.Category", on_delete=models.CASCADE, related_name="size_guides", null=True, blank=True,
    )
    title = models.CharField(max_length=160)
    source_label = models.CharField(max_length=200, blank=True)
    source_url = models.URLField(max_length=500, blank=True)
    instructions = models.TextField(blank=True, validators=[MaxLengthValidator(3000)])
    is_published = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["brand", "category"], name="catalog_unique_brand_category_guide"),
            models.UniqueConstraint(
                fields=["brand"], condition=models.Q(category__isnull=True),
                name="catalog_unique_brand_general_guide",
            ),
            models.CheckConstraint(
                condition=models.Q(is_published=False) | ~models.Q(source_label="") | ~models.Q(source_url=""),
                name="catalog_published_guide_has_source",
            ),
        ]

    def clean(self):
        super().clean()
        if self.is_published and not (self.source_label.strip() or self.source_url.strip()):
            raise ValidationError({"source_label": "A published size guide requires a source."})

    def __str__(self):
        return f"{self.brand}: {self.title}"
