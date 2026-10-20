from django.db import models


class AuthorizationFlow(models.Model):
    invitation = models.ForeignKey("ebay_oauth.Invitation", on_delete=models.CASCADE)
    state_hash = models.CharField(max_length=64, unique=True)
    browser_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
