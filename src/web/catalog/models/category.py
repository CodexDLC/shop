from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _


class Category(models.Model):
    slug = models.SlugField(unique=True)
    name_key = models.CharField(max_length=160)
    section = models.CharField(
        max_length=12,
        choices=[("underwear", _("Unterwäsche")), ("swimwear", _("Bademode")), ("other", _("Sonstiges"))],
        default="other",
    )
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT,
                               related_name="children")
    name_de = models.CharField(max_length=160, blank=True)
    name_ru = models.CharField(max_length=160, blank=True)
    description_de = models.TextField(blank=True)
    description_ru = models.TextField(blank=True)
    seo_title = models.CharField(max_length=160, blank=True)
    seo_description = models.CharField(max_length=320, blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    is_visible = models.BooleanField(default=True)
    image = models.FileField(upload_to="categories/", blank=True)
    image_alt = models.CharField(max_length=200, blank=True)

    @property
    def name(self):
        from web.localization import translate_text

        if (get_language() or "de").startswith("ru") and self.name_ru:
            return self.name_ru
        legacy = translate_text(self.name_key) if self.name_key else ""
        return self.name_de or (legacy if legacy and legacy != f"[{self.name_key}]" else self.slug.replace("-", " ").capitalize())

    @property
    def description(self):
        return self.description_ru if (get_language() or "de").startswith("ru") and self.description_ru else self.description_de

    def clean(self):
        super().clean()
        from web.localization import translate_text

        parents = dict(type(self).objects.values_list("pk", "parent_id"))
        seen = {self.pk} if self.pk else set()
        current = self.parent_id
        while current:
            if current in seen:
                raise ValidationError({"parent": translate_text("staff.categories.cycle")})
            seen.add(current)
            current = parents.get(current)
        if self.parent_id and type(self).objects.filter(pk=self.parent_id).exclude(section=self.section).exists():
            raise ValidationError({"parent": translate_text("staff.categories.section_mismatch")})
        if self.pk and self.children.exclude(section=self.section).exists():
            raise ValidationError({"section": translate_text("staff.categories.section_mismatch")})

    def __str__(self):
        return self.name
