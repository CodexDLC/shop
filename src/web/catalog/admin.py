from django.contrib import admin

from .category_admin import CategoryAdmin
from .models import (
    Brand,
    Category,
    Material,
    Product,
    ProductImage,
    ProductInformation,
    ProductProperty,
    ProductReview,
    ProductVariant,
    SizeGuide,
    SizeGuideRow,
    Tag,
)
from .readonly_product_admin import ReadonlyProductAdmin

admin.site.register([
    Brand, Material, ProductProperty, ProductReview,
    SizeGuide, SizeGuideRow, Tag,
])
admin.site.register([Product, ProductImage, ProductInformation, ProductVariant], ReadonlyProductAdmin)
admin.site.register(Category, CategoryAdmin)
