from web.catalog.models import (
    Brand,
    Category,
    Material,
    ProductImage,
    ProductProperty,
    ProductReview,
    SizeGuide,
    Tag,
)

RESOURCES = {
    "brands": (Brand, "brand", ["name", "slug"]),
    "categories": (Category, "category", ["slug", "name_key", "section"]),
    "materials": (Material, "material", ["name", "slug"]),
    "properties": (ProductProperty, "property", ["name", "slug"]),
    "tags": (Tag, "tag", ["slug", "label_key"]),
    "size_guides": (SizeGuide, "size_guide", [
        "brand", "category", "title", "source_label", "source_url", "instructions", "is_published",
    ]),
    "reviews": (ProductReview, "review", []),
    "photos": (ProductImage, "photo", []),
}
