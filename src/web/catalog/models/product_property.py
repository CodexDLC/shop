from django.db import models


class ProductProperty(models.Model):
    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=160)

    def __str__(self):
        return self.name
