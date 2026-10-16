from django.db import models


class Category(models.Model):
    slug = models.SlugField(unique=True)
    name_key = models.CharField(max_length=160)

    def __str__(self):
        return self.slug
