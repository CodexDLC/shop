from django.db import models
from django.utils.translation import gettext_lazy as _


class Category(models.Model):
    slug = models.SlugField(unique=True)
    name_key = models.CharField(max_length=160)
    section = models.CharField(
        max_length=12,
        choices=[("underwear", _("Unterwäsche")), ("swimwear", _("Bademode")), ("other", _("Sonstiges"))],
        default="other",
    )

    def __str__(self):
        return self.slug
