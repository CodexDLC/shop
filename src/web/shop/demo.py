def homepage_demo():
    """Presentation-only fixtures; no stock, payment or marketplace operations."""
    categories = [
        {"slug": "boxer", "name": "Boxershorts"},
        {"slug": "slip", "name": "Slips & Pants"},
        {"slug": "string", "name": "Strings"},
        {"slug": "body", "name": "Bodies"},
    ]
    products = [
        {"id": "c1", "brand": "CALIDA", "name": "Essential · Boxer Pants", "category": "boxer", "price": "39,90", "tag": "Komfort für jeden Tag"},
        {"id": "o1", "brand": "OLAF BENZ", "name": "RED 2320 · Mini Slip", "category": "slip", "price": "29,90", "tag": "Leicht. Präzise. Zeitlos."},
        {"id": "m2", "brand": "MANSTORE", "name": "M102 · Micro String", "category": "string", "price": "24,90", "tag": "Weniger Stoff. Mehr Stil."},
        {"id": "m3", "brand": "MANSTORE", "name": "M101 · Body", "category": "body", "price": "59,90", "tag": "Eine besondere Silhouette"},
    ]
    return {"categories": categories, "products": products}
