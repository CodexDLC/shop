from django.db import models


class CartLine(models.Model):
    cart = models.ForeignKey("cart.Cart", related_name="lines", on_delete=models.CASCADE)
    sku = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cart", "sku"], name="cart_unique_sku"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="cart_quantity_positive"),
        ]
