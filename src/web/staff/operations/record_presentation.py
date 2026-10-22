"""Explicit read-only staff cards; no model introspection or provider payloads."""

from django.urls import reverse

from .order_presentation import postal_address
from .presentation import audit_action, audit_object, detail_fields, field, money, state, translated_name


def record_card(kind, obj, user):
    fields = detail_fields(kind, obj, user)
    technical = []
    title = f"#{obj.pk}"
    addresses = None
    refunds = None
    if kind in {"customers", "team"}:
        title = obj.get_full_name() or obj.username
    elif kind == "stock":
        title = obj.sku
        fields[-1] = field("colour", translated_name(obj.color_name_key, obj.color_code))
        if user.has_perm("catalog.change_product"):
            fields[1]["url"] = reverse("staff:product_edit", kwargs={"pk": obj.product_id})
    elif kind == "support":
        title = obj.name or title
    elif kind == "promos":
        title = obj.code
    elif kind == "payments":
        technical = [field("reference", str(obj.operation_id))]
        fields = fields[1:]
        if user.has_perm("orders.view_order"):
            fields[0]["url"] = reverse("staff:order_detail", kwargs={"pk": obj.order_id})
    elif kind == "audit":
        title = audit_action(obj.action)
        fields = [field("object", audit_object(obj)), field("created", obj.created_at)]
        if user.has_perm("auth.view_user") and obj.actor_id:
            fields.append(field("actor", obj.actor.get_full_name() or obj.actor.username))
        technical = [field("action", obj.action), field("object", f"{obj.object_type} #{obj.object_id}")]
    if kind == "customers" and user.has_perm("customer.view_customeraddress"):
        addresses = [postal_address({"first_name": a.recipient, "street": a.street_address,
                     "postal_code": a.postal_code, "city": a.city, "country": a.country,
                     "shipping_type": a.kind, "post_number": a.post_number,
                     "packstation_number": a.station_number}) for a in obj.customer_addresses.all()]
    if kind == "payments" and user.has_perm("payments.view_refundattempt"):
        refunds = [{"id": r.pk, "status": state(r.status)["value"],
                    "amount": money(r.amount, obj.currency), "created": r.created_at, "reference": str(r.operation_id)}
                   for r in obj.refund_attempts.all()]
    content = [f for f in fields if f["label"] == "staff.records.message"]
    return {"title": title, "fields": [f for f in fields if f not in content and f["value"] not in ("", None)], "content": content,
            "technical": technical, "addresses": addresses, "refunds": refunds}
