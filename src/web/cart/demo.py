"""Synthetic presentation fixtures: never persist, reserve stock or call providers."""
from decimal import Decimal


def get_cart_demo_context():
    return {
        "demo_mode": True,
        "cart": {
            "currency": "EUR",
            "lines": [{
                "sku": "DEMO-M107-BLACK-M", "brand": "MANSTORE", "name": "M107 Deep V Boxer",
                "colour_key": "colour.black", "size": "M", "quantity": 1,
                "unit_amount": Decimal("49.95"), "line_amount": Decimal("49.95"),
            }, {
                "sku": "DEMO-CALIDA-L", "brand": "CALIDA", "name": "Natural Skin Boxer Brief",
                "colour_key": "catalog.color.black", "size": "L", "quantity": 1,
                "unit_amount": Decimal("44.95"), "line_amount": Decimal("44.95"),
            }, {
                "sku": "DEMO-OLAF-M", "brand": "Olaf Benz", "name": "RED 2004 Mini-Pant",
                "colour_key": "catalog.color.navy", "size": "M", "quantity": 1,
                "unit_amount": Decimal("44.90"), "line_amount": Decimal("44.90"),
            }],
            "subtotal": Decimal("139.80"), "total": Decimal("139.80"),
        },
    }
