from django.urls import reverse
from django.utils.formats import number_format

from web.localization.translation import translate_text

from .registry import detail_route


def cell(value, *, key=False, url=""):
    return {"value": value, "key": key, "url": url}


def field(label, value, *, key=False, url=""):
    return {"label": f"staff.records.{label}", **cell(value, key=key, url=url)}


def state(value):
    if value not in {"draft", "awaiting_payment", "confirmed", "cancelled", "test_created",
                     "created", "pending", "succeeded", "failed", "unknown", "requested"}:
        value = "unknown"
    return cell(f"staff.records.status.{value}", key=True)


def active(value):
    return cell("staff.records.active" if value else "staff.records.inactive", key=True)


def money(value, currency):
    symbol = {"EUR": "€", "USD": "$", "GBP": "£"}.get(currency, currency)
    return f"{number_format(value, decimal_pos=2, use_l10n=True)} {symbol}" if value is not None else "—"


def columns(kind):
    return [f"staff.records.{name}" for name in {
        "orders": ("reference", "status", "total", "items", "created", "mode"),
        "customers": ("username", "email", "name", "status", "created"),
        "support": ("reference", "topic", "name", "email", "status", "created"),
        "stock": ("sku", "product", "size", "quantity", "price", "status"),
        "payments": ("reference", "order", "method", "status", "amount", "mode"),
        "promos": ("code", "kind", "value", "minimum", "status"),
        "audit": ("reference", "action", "object", "actor", "created"),
        "team": ("username", "email", "name", "status", "owner"),
    }[kind]]


def summary(kind, obj, user=None):
    if kind == "orders":
        return [cell(f"#{obj.pk}"), state(obj.status), cell(money(obj.total_amount, obj.currency)),
                cell(obj.item_count), cell(obj.created_at), cell("staff.records.test" if obj.is_test
                                                               else "staff.records.standard", key=True)]
    if kind in ("customers", "team"):
        return [cell(obj.username), cell(obj.email), cell(obj.get_full_name()), active(obj.is_active),
                cell(obj.date_joined) if kind == "customers" else
                cell("staff.records.yes" if obj.is_superuser else "staff.records.no", key=True)]
    if kind == "support":
        topic = obj.topic if obj.topic in {"retoure", "versand", "groesse", "zahlung", "reklamation"} else "sonstiges"
        return [cell(f"#{obj.pk}"), cell(f"staff.records.topic.{topic}", key=True), cell(obj.name), cell(obj.email),
                cell("staff.records.resolved" if obj.resolved else "staff.records.open", key=True),
                cell(obj.created_at)]
    if kind == "stock":
        return [cell(obj.sku), cell(f"{obj.product.brand.name} {obj.product.model_name}"), cell(obj.size),
                cell(obj.demo_quantity), cell(money(obj.price, obj.currency)), active(obj.is_active)]
    if kind == "payments":
        return [cell(f"#{obj.pk}"), cell(f"#{obj.order_id}"),
                cell(f"staff.records.method.{obj.method if obj.method in {'card', 'paypal'} else 'unknown'}", key=True), state(obj.status),
                cell(money(obj.amount, obj.currency)), cell(f"staff.records.mode.{obj.mode if obj.mode in {'demo', 'sandbox'} else 'demo'}", key=True)]
    if kind == "promos":
        return [cell(obj.code), cell(f"staff.records.kind.{obj.kind}", key=True),
                cell(f"{obj.value}%" if obj.kind == "percent" else money(obj.value, obj.currency)),
                cell(money(obj.min_subtotal, obj.currency)), active(obj.is_active)]
    if kind == "audit":
        return [cell(f"#{obj.pk}"), cell(audit_action(obj.action)), cell(audit_object(obj)),
                cell((obj.actor.get_full_name() or obj.actor.username) if obj.actor_id and user and user.has_perm("auth.view_user") else "—"), cell(obj.created_at)]
    raise ValueError(kind)


def table_row(kind, obj, user=None):
    cells = summary(kind, obj, user)
    cells[0]["url"] = reverse(f"staff:{detail_route(kind)}", kwargs={"pk": obj.pk})
    return cells


def detail_fields(kind, obj, user):
    values = summary(kind, obj)
    result = [{"label": label, **value} for label, value in zip(columns(kind), values, strict=True)]
    if kind == "orders":
        result += [field("subtotal", money(obj.subtotal_amount, obj.currency)),
                   field("discount", money(obj.discount_amount, obj.currency)),
                   field("shipping", money(obj.shipping_amount, obj.currency)), field("code", obj.coupon_code)]
        if user.has_perm("auth.view_user") and obj.user_id:
            result += [field("customer", obj.user.email)]
    elif kind == "stock":
        result += [field("colour", obj.color_name_key, key=True)]
    elif kind == "support":
        result += [field("message", obj.message)]
    elif kind == "promos":
        result += [field("starts", obj.starts_at), field("ends", obj.ends_at)]
    elif kind == "team":
        if user.has_perm("auth.view_group"):
            result += [field("groups", ", ".join(group.name for group in obj.groups.all()))]
        result += [field("last_login", obj.last_login)]
    return result


def address_fields(address):
    # Explicit snapshot allowlist: unexpected JSON keys can never expose credentials.
    allowed = ("email", "first_name", "last_name", "street", "postal_code", "city", "country",
               "shipping_type", "post_number", "packstation_number")
    if not isinstance(address, dict):
        return []
    return [field(key, address[key]) for key in allowed if address.get(key)]


def translated_name(key, fallback):
    value = translate_text(key) if key else ""
    return value if value and value != key and not value.startswith("[") else fallback


def audit_action(action):
    known = {"promo.updated", "promo.created", "support.resolved", "support.reopened",
             "quick_access.updated", "store_identity.updated", "product.information_updated", "product.created",
             "product.updated", "product.submit", "product.publish", "product.withdraw",
             "variants.updated", "photos.create", "photos.add", "photos.delete", "photos.reorder",
             "photos.update", "product.review", "product.reject"}
    known.update(f"reference.{name}.saved" for name in
                 ("brand", "category", "material", "property", "tag", "size_guide"))
    known.update(f"seo.{kind}.{action}" for kind in ("page", "rule")
                 for action in ("save", "publish", "restore"))
    return translate_text(f"staff.cards.action.{action}" if action in known else "staff.cards.action.other")


def audit_object(obj):
    names = {"catalog.product": "product", "catalog.brand": "brand", "catalog.category": "category",
             "catalog.material": "material", "catalog.productproperty": "property", "catalog.tag": "tag",
             "catalog.sizeguide": "size_guide", "cart.promocode": "promo",
             "support.contactticket": "support", "staff.cabinetpreferences": "preferences",
             "shop.storeidentity": "store_identity", "seo.seopage": "seo_page", "seo.seorule": "seo_rule"}
    return f"{translate_text('staff.cards.object.' + names.get(obj.object_type, 'other'))} #{obj.object_id}"
