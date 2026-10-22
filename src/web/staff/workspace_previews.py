"""Allowlisted, explicitly non-operational workspace designs."""

PREVIEWS = {
    "shipping": ("operations", "orders.view_order", ("labels", "pickup", "tracking")),
    "returns": ("operations", "orders.view_order", ("return_request", "return_label", "inspection")),
    "operations_settings": ("operations", "orders.view_order", ("shipping_rules", "packing", "return_rules")),
    "analytics": ("management", "staff.change_cabinetpreferences", ("sales", "sources", "profit")),
    "content": ("management", "staff.change_cabinetpreferences", ("homepage", "legal", "email")),
    "integrations": ("management", "staff.change_cabinetpreferences", ("ebay", "stripe", "dhl", "mail", "s3")),
    "store_settings": ("management", "staff.change_cabinetpreferences", ("company", "taxes", "documents", "notifications")),
}
