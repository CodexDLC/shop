from django.contrib import admin

from .models import Brand, Category, Product, ProductImage, ProductVariant, Tag

admin.site.register([Brand, Category, Product, ProductImage, ProductVariant, Tag])
