from django.db import models


class SeoPage(models.Model):
    kind = models.CharField(max_length=12)
    key = models.CharField(max_length=160)
    language = models.CharField(max_length=2, choices=[("de", "Deutsch"), ("ru", "Русский")])
    draft = models.JSONField(default=dict)
    published = models.JSONField(default=dict)
    previous = models.JSONField(null=True, default=None)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ("view",)
        permissions = [
            ("change_metadata", "Can edit SEO metadata"),
            ("change_text", "Can edit SEO page texts"),
            ("manage_rules", "Can manage automatic SEO rules"),
            ("publish_seo", "Can publish SEO changes"),
        ]
        constraints = [models.UniqueConstraint(fields=["kind", "key", "language"], name="seo_page_target_language")]
