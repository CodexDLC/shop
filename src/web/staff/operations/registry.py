from django.contrib.auth import get_user_model

from web.cart.models import PromoCode
from web.catalog.models import ProductVariant
from web.orders.models import Order
from web.payments.models import PaymentAttempt
from web.staff.models import StaffAuditEvent
from web.support.models import ContactTicket


def record_model(kind):
    return {
        "orders": Order, "customers": get_user_model(), "support": ContactTicket,
        "stock": ProductVariant, "payments": PaymentAttempt, "promos": PromoCode,
        "audit": StaffAuditEvent, "team": get_user_model(),
    }[kind]


def record_permission(kind):
    model = record_model(kind)
    return f"{model._meta.app_label}.view_{model._meta.model_name}"


def detail_route(kind):
    return {"orders": "order_detail", "customers": "customer_detail", "support": "support_detail",
            "stock": "stock_detail", "payments": "payment_detail", "promos": "promo_detail",
            "audit": "audit_detail", "team": "team_detail"}[kind]


def status_options(kind):
    if kind in ("orders", "payments"):
        return [(value, f"staff.records.status.{value}")
                for value, _ in record_model(kind)._meta.get_field("status").choices]
    if kind == "support":
        return [("open", "staff.records.open"), ("resolved", "staff.records.resolved")]
    if kind in ("stock", "promos", "customers", "team"):
        return [("active", "staff.records.active"), ("inactive", "staff.records.inactive")]
    return []
