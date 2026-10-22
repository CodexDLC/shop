"""Allowlisted settings designs and links; no operational settings payloads."""
from django.urls import reverse


def settings_workspace(user, section):
    definitions = {
        "store_settings": (
            ("company", (("company_name", "text"), ("company_email", "email"), ("company_address", "textarea")), ()),
            ("taxes", (("vat_id", "text"), ("price_display", "select"), ("currency", "select")), ()),
            ("documents", (("document_prefix", "text"), ("legal_provider", "text")),
             (("support:legal", "staff.workspace.capability.legal", "staff.change_cabinetpreferences"),)),
            ("languages", (("default_language", "select"), ("notification_email", "email")), ()),
        ),
        "catalog": (
            ("structure", (("default_visibility", "select"),), (
                ("staff:categories", "staff.workspace.nav.categories", "catalog.view_category"),
                ("staff:brands", "staff.workspace.nav.brands", "catalog.view_brand"),
                ("staff:tags", "staff.workspace.nav.tags", "catalog.view_tag"))),
            ("attributes", (("required_attributes", "textarea"),), (
                ("staff:materials", "staff.workspace.nav.materials", "catalog.view_material"),
                ("staff:properties", "staff.workspace.nav.properties", "catalog.view_productproperty"),
                ("staff:size_guides", "staff.workspace.nav.size_guides", "catalog.view_sizeguide"))),
            ("publication", (("photo_requirements", "textarea"), ("review_rule", "select")), (
                ("staff:products", "staff.nav.products", "catalog.view_product"),
                ("staff:photos", "staff.workspace.nav.photos", "catalog.view_productimage"))),
        ),
        "operations_settings": (
            ("shipping", (("shipping_country", "select"), ("free_shipping_threshold", "number")), (
                ("staff:orders", "staff.workspace.nav.orders", "orders.view_order"),)),
            ("packing", (("parcel_weight", "number"), ("packing_note", "textarea")), (
                ("staff:stock", "staff.workspace.nav.stock", "catalog.view_productvariant"),)),
            ("returns", (("return_days", "number"), ("inspection_rule", "select")), ()),
        ),
    }
    cards = []
    for name, fields, links in definitions.get(section, ()):
        cards.append({"key": name, "title": f"staff.settings_workspace.card.{name}",
                      "description": f"staff.settings_workspace.card.{name}.description",
                      "fields": [{"key": key, "type": kind, "label": f"staff.settings_workspace.field.{key}"}
                                 for key, kind in fields],
                      "links": [{"url": reverse(url), "label": label} for url, label, permission in links
                                if user.has_perm(permission)]})
    nav = []
    for name, url, permission in (
        ("store_settings", reverse("staff:workspace_preview", kwargs={"section": "store_settings"}), "staff.change_cabinetpreferences"),
        ("catalog", reverse("staff:catalog_settings"), "catalog.view_product"),
        ("operations_settings", reverse("staff:workspace_preview", kwargs={"section": "operations_settings"}), "orders.view_order"),
        ("quick_access", reverse("staff:settings"), "staff.change_cabinetpreferences"),
    ):
        if user.has_perm(permission):
            nav.append({"url": url, "label": f"staff.settings_workspace.nav.{name}", "active": section == name})
    return {"settings_cards": cards, "settings_navigation": nav,
            "settings_title": f"staff.settings_workspace.nav.{section}",
            "settings_intro": f"staff.settings_workspace.intro.{section}"}
