from django.db import models


class DeletionReceipt(models.Model):
    notification_id = models.CharField(max_length=200, unique=True)
    topic = models.CharField(max_length=64)
    schema_version = models.CharField(max_length=20)
    event_date = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    payload_fingerprint = models.CharField(max_length=64)
    user_fingerprint = models.CharField(max_length=64)
    status = models.CharField(max_length=32, default="review_required", editable=False)

    class Meta:
        ordering = ("received_at",)
