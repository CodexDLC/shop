"""Presentation-only fixtures; catalog models/seed are a separate data source."""
from decimal import Decimal


def get_catalog_demo_context():
    rows = (
        ('p1', 'MANSTORE', 'M2223 Bungee Pants', '49.95', 'R0wAAeSwAGRqvDOf'),
        ('p2', 'Olaf Benz', 'RED2260 Minipants', '44.90', 'lrQAAeSw-UZqvsIf'),
        ('p3', 'CALIDA', 'Cotton Code Boxer Brief', '29.95', 'f98AAeSwBGFqxLls'),
        ('p4', 'MANSTORE', 'M101 Ultra Body', '79.00', None),
    )
    products = {
        code: {'code': code, 'brand': brand, 'name': name, 'price': Decimal(price),
               'photo_url': f'https://i.ebayimg.com/images/g/{photo}/s-l1600.webp' if photo else '',
               'is_demo': True}
        for code, brand, name, price, photo in rows
    }
    return {'catalog_products': list(products.values()), 'products': products}
