from django.db import models


class SellerConnection(models.Model):
    seller = models.CharField(max_length=100, unique=True)
    encrypted_access_token = models.TextField()
    encrypted_refresh_token = models.TextField()
    access_expires_at = models.DateTimeField()
    refresh_expires_at = models.DateTimeField()
    connected_at = models.DateTimeField(auto_now=True)
    scopes = models.JSONField(default=list)
