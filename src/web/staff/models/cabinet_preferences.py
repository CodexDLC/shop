from django.db import models


class CabinetPreferences(models.Model):
    """Shared navigation preferences, not a generic site-settings payload."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    quick_access_keys = models.JSONField(default=list, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="staff_single_preferences")]
