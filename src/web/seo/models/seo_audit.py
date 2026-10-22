from django.conf import settings
from django.db import models


class SeoAudit(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    target = models.CharField(max_length=190)
    language = models.CharField(max_length=2)
    action = models.CharField(max_length=24)
    fields = models.JSONField(default=list)
    version = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ["-created_at", "-pk"]
