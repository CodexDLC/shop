from django.db import models


class Tag(models.Model):
    slug = models.SlugField(unique=True)
    label_key = models.CharField(max_length=160)

    def __str__(self):
        return self.slug
