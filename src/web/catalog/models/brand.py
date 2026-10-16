from django.db import models


class Brand(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=120)

    def __str__(self):
        return self.name
