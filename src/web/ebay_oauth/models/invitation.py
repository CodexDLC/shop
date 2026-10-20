from django.db import models


class Invitation(models.Model):
    token_hash = models.CharField(max_length=64, unique=True)
    expected_seller = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
