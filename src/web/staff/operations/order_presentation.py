"""Allowlisted order snapshots for the read-only staff workspace."""

from urllib.parse import urlsplit

from django.utils.formats import number_format

from .presentation import state


def order_money(amount, currency):
    symbol = {"EUR": "€", "USD": "$", "GBP": "£"}.get(currency, currency)
    return f"{number_format(amount, decimal_pos=2, use_l10n=True)} {symbol}" if amount is not None else "—"


def has_distinct_update(created, updated):
    return created.replace(second=0, microsecond=0) != updated.replace(second=0, microsecond=0)


def postal_address(snapshot):
    if not isinstance(snapshot, dict):
        return None
    # Never render an entire JSON object, including unexpected nested values.
    keys = ("first_name", "last_name", "street", "postal_code", "city", "country", "email",
            "shipping_type", "post_number", "packstation_number")
    data = {key: str(snapshot[key]) for key in keys
            if isinstance(snapshot.get(key), (str, int)) and snapshot[key] != ""}
    if not data:
        return None
    return {"name": " ".join(filter(None, [data.get("first_name"), data.get("last_name")])),
            "street": data.get("street", ""),
            "locality": " ".join(filter(None, [data.get("postal_code"), data.get("city")])),
            "country": data.get("country", ""), "email": data.get("email", ""),
            "packstation": data.get("shipping_type") == "packstation",
            "station": data.get("packstation_number", ""), "post_number": data.get("post_number", "")}


def order_context(order, user):
    lines = []
    for line in order.lines.all():
        # A snapshot URL is data, never executable markup or a replacement catalogue lookup.
        try:
            photo = urlsplit(line.photo_url)
            valid_photo = (photo.scheme in {"http", "https"} and photo.netloc) or (
                line.photo_url.startswith("/") and not line.photo_url.startswith("//")
                and "\\" not in line.photo_url)
        except ValueError:
            valid_photo = False
        safe_photo = line.photo_url if valid_photo else ""
        lines.append({"sku": line.sku, "name": line.product_name, "brand": line.brand_name,
                      "colour": line.colour_name, "size": line.size_name, "quantity": line.quantity,
                      "photo_url": safe_photo, "unit": order_money(line.unit_amount, order.currency),
                      "total": order_money(line.line_amount, order.currency)})
    payments = []
    if user.has_perm("payments.view_paymentattempt"):
        for attempt in order.payment_attempts.all():
            method = attempt.method if attempt.method in {"card", "paypal"} else "unknown"
            payments.append({"created_at": attempt.created_at, "updated_at": attempt.updated_at,
                             "show_updated": has_distinct_update(attempt.created_at, attempt.updated_at),
                             "status": state(attempt.status)["value"],
                             "method": f"staff.records.method.{method}",
                             "amount": order_money(attempt.amount, attempt.currency),
                             "mode": "staff.records.mode.sandbox" if attempt.mode == "sandbox"
                                     else "staff.records.mode.demo"})
    data = {"id": order.pk, "reference": str(order.reference), "status": state(order.status)["value"],
            "created_at": order.created_at, "updated_at": order.updated_at, "is_test": order.is_test,
            "show_updated": has_distinct_update(order.created_at, order.updated_at),
            "lines": lines, "payments": payments, "coupon": order.coupon_code,
            "totals": [{"label": f"staff.records.{label}", "value": order_money(amount, order.currency)}
                       for label, amount in (("subtotal", order.subtotal_amount),
                                             ("discount", order.discount_amount),
                                             ("shipping", order.shipping_amount))],
            "total": order_money(order.total_amount, order.currency),
            "can_view_addresses": user.has_perm("customer.view_customeraddress")}
    if data["can_view_addresses"]:
        data["shipping"] = postal_address(order.address)
        data["billing"] = postal_address(order.billing_address)
    if user.has_perm("auth.view_user") and order.user_id:
        data["customer_email"] = order.user.email
    return data
