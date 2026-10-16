"""Local mock only. Not Stripe sandbox API, no provider credentials or webhooks."""


def get_payment_demo_context():
    return {
        "demo_mode": True,
        "payment": {
            "provider": "stripe", "mode": "demo", "checkout": "hosted",
            "methods": [
                {"code": "card", "label_key": "payment.method.card"},
                {"code": "paypal", "label_key": "payment.method.paypal"},
            ],
            "status_key": "payment.status.demo", "can_charge": False, "can_refund": False,
        },
    }
