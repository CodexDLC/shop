"""Allowlisted catalogue detail projection, independent of concrete model fields."""

from urllib.parse import urlsplit

from web.localization.translation import translate_text
from web.staff.operations.presentation import translated_name


def resource_label(resource, obj):
    if resource == "tags":
        return translated_name(obj.label_key, obj.slug)
    if resource in {"reviews", "photos"}:
        return f"{obj.product.brand.name} · {obj.product.model_name}"
    if resource == "size_guides":
        return obj.title
    return obj.name


def safe_photo(url):
    try:
        parsed = urlsplit(url)
        return url if ((parsed.scheme in {"https", "http"} and parsed.netloc)
                       or (url.startswith("/") and not url.startswith("//") and "\\" not in url)) else ""
    except ValueError:
        return ""


def resource_card(resource, obj):
    names = {
        "brands": ("name",), "materials": ("name",), "properties": ("name",),
        "tags": (), "size_guides": ("title", "source_label", "instructions", "is_published"),
        "reviews": ("author_display", "rating", "body", "status", "created_at"),
        "photos": ("color_code", "alt_text", "position"),
    }[resource]
    values = []
    for name in names:
        value = getattr(obj, name)
        if value in ("", None):
            continue
        if name == "status":
            value = translate_text(f"staff.workspace_catalog.status.{value}")
        elif isinstance(value, bool):
            value = translate_text("staff.workspace_catalog.yes" if value else "staff.workspace_catalog.no")
        values.append((f"staff.workspace_catalog.field.{name}", value))
    if resource == "size_guides":
        values.insert(0, ("staff.workspace_catalog.field.brand", obj.brand.name))
        if obj.category_id:
            values.insert(1, ("staff.workspace_catalog.field.category", obj.category.name))
    technical = []
    if resource == "size_guides" and obj.source_url:
        technical.append(("staff.workspace_catalog.field.source_url", obj.source_url))
    if hasattr(obj, "slug"):
        technical.append(("staff.workspace_catalog.field.slug", obj.slug))
    return {"values": values, "technical": technical,
            "photo": safe_photo(obj.public_url) if resource == "photos" else ""}
