from django.core.validators import MaxLengthValidator, MaxValueValidator, MinValueValidator
from django.db import models


class ProductReview(models.Model):
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    author_display = models.CharField(max_length=80, blank=True)
    body = models.TextField(blank=True, validators=[MaxLengthValidator(3000)])
    status = models.CharField(
        max_length=10, choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")],
        default="pending", db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name="catalog_review_rating"),
            models.CheckConstraint(
                condition=models.Q(status__in=["pending", "approved", "rejected"]), name="catalog_review_status",
            ),
        ]

    def __str__(self):
        return f"{self.product} ({self.rating}/5, {self.status})"
