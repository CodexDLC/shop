from django.conf import settings
from django.db import models


class ContactTicket(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=120)
    email = models.EmailField(max_length=254)
    topic = models.CharField(max_length=30)
    message = models.TextField(max_length=4000)
    resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Kontakt #{self.pk}"
