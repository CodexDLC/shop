from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from web.catalog.models import Brand, Category, Product, ProductImage, ProductVariant, Tag

DEMO_PRODUCTS = (
    ("manstore-m2223", "MANSTORE", "slips", "M2223 Bungee Pants", "49.95", "R0wAAeSwAGRqvDOf"),
    ("olaf-benz-red2260", "Olaf Benz", "boxershorts", "RED2260 Minipants", "44.90", "lrQAAeSw-UZqvsIf"),
    ("calida-cotton-code", "CALIDA", "slips", "Cotton Code Boxer Brief", "29.95", "f98AAeSwBGFqxLls"),
    ("olaf-benz-red2059", "Olaf Benz", "strings", "RED2059 Ministring", "34.90", "SN0AAeSwwD1qv9bW"),
)


class Command(BaseCommand):
    help = "Create/update explicitly illustrative catalog data; never call a payment or channel API."

    @transaction.atomic
    def handle(self, *args, **options):
        categories = {}
        for slug in ("boxershorts", "slips", "strings", "bodies"):
            categories[slug], _ = Category.objects.update_or_create(
                slug=slug, defaults={"name_key": f"catalog.category.{slug}"}
            )
        demo_tag, _ = Tag.objects.update_or_create(
            slug="demo", defaults={"label_key": "catalog.tag.demo"}
        )
        for slug, brand_name, category, model_name, price, photo in DEMO_PRODUCTS:
            brand, _ = Brand.objects.get_or_create(
                slug=brand_name.lower().replace(" ", "-"), defaults={"name": brand_name}
            )
            product, _ = Product.objects.update_or_create(slug=slug, defaults={
                "brand": brand, "category": categories[category], "model_name": model_name,
                "description_key": "catalog.product.demo_description", "is_active": True,
            })
            product.tags.add(demo_tag)
            for color, hex_value in (("black", "#171E19"), ("navy", "#223047")):
                for size in ("S", "M", "L", "XL"):
                    ProductVariant.objects.update_or_create(
                        sku=f"DEMO-{slug.upper()}-{color.upper()}-{size}", defaults={
                            "product": product, "color_code": color, "color_hex": hex_value,
                            "color_name_key": f"catalog.color.{color}", "size": size,
                            "price": Decimal(price), "currency": "EUR", "is_active": True,
                            "demo_quantity": 0 if size == "XL" else 3,
                        }
                    )
            # Real source photo, general gallery: no invented colour-specific photographs.
            ProductImage.objects.update_or_create(product=product, color_code="", position=0, defaults={
                "image_url": f"https://i.ebayimg.com/images/g/{photo}/s-l1600.webp",
                "alt_key": f"catalog.photo.{slug}",
            })
        self.stdout.write(self.style.SUCCESS("Demo catalog ready: 4 products, 32 illustrative variants."))
