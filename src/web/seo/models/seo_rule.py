from django.db import models


class SeoRule(models.Model):
    kind = models.CharField(max_length=12)
    language = models.CharField(max_length=2, choices=[("de", "Deutsch"), ("ru", "Русский")])
    draft = models.JSONField(default=dict)
    published = models.JSONField(default=dict)
    previous = models.JSONField(null=True, default=None)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=["kind", "language"], name="seo_rule_kind_language")]
