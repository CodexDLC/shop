"""Order screen fixture; does not create an order or claim a real payment/shipment."""
from web.cart.demo import get_cart_demo_context


def get_order_demo_context():
    cart = get_cart_demo_context()["cart"]
    return {
        "demo_mode": True,
        "order": {
            "reference": "DEMO-MM-849204", "status_key": "order.status.demo",
            "currency": cart["currency"], "lines": cart["lines"], "total": cart["total"],
            "tracking_number": None,
        },
    }
