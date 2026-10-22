from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class SizeGuideRow(models.Model):
    guide = models.ForeignKey("catalog.SizeGuide", on_delete=models.CASCADE, related_name="rows")
    size = models.CharField(max_length=30)
    position = models.PositiveIntegerField(default=0)
    waist_min_cm = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0.01"))],
    )
    waist_max_cm = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0.01"))],
    )
    hip_min_cm = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0.01"))],
    )
    hip_max_cm = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0.01"))],
    )

    class Meta:
        ordering = ["position", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["guide", "size"], name="catalog_unique_guide_size"),
            models.CheckConstraint(
                condition=(models.Q(waist_min_cm__isnull=True, waist_max_cm__isnull=True)
                           | models.Q(waist_min_cm__isnull=False, waist_max_cm__isnull=False,
                                      waist_min_cm__gt=0, waist_max_cm__gte=models.F("waist_min_cm"))),
                name="catalog_valid_guide_waist",
            ),
            models.CheckConstraint(
                condition=(models.Q(hip_min_cm__isnull=True, hip_max_cm__isnull=True)
                           | models.Q(hip_min_cm__isnull=False, hip_max_cm__isnull=False,
                                      hip_min_cm__gt=0, hip_max_cm__gte=models.F("hip_min_cm"))),
                name="catalog_valid_guide_hip",
            ),
            models.CheckConstraint(
                condition=models.Q(waist_min_cm__isnull=False) | models.Q(hip_min_cm__isnull=False),
                name="catalog_guide_row_has_dimension",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        for dimension in ("waist", "hip"):
            minimum = getattr(self, f"{dimension}_min_cm")
            maximum = getattr(self, f"{dimension}_max_cm")
            try:
                minimum = Decimal(minimum) if minimum is not None else None
                maximum = Decimal(maximum) if maximum is not None else None
            except (InvalidOperation, TypeError, ValueError):
                continue  # Field validation reports malformed decimal values.
            if any(value is not None and not value.is_finite() for value in (minimum, maximum)):
                continue  # DecimalField reports non-finite values.
            if (minimum is None) != (maximum is None):
                errors[f"{dimension}_min_cm"] = "Provide both bounds or leave both empty."
            elif minimum is not None and (minimum <= 0 or maximum < minimum):
                errors[f"{dimension}_min_cm"] = "Measurements must be positive and ordered."
        if self.waist_min_cm is None and self.hip_min_cm is None:
            errors["waist_min_cm"] = "Provide at least one measurement dimension."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.guide}: {self.size}"
