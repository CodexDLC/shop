"""Build immutable order address snapshots from validated checkout data."""


def shipping_address(data):
    fields = ("email", "first_name", "last_name", "street", "postal_code", "city", "country",
              "shipping_type", "post_number", "packstation_number")
    return {name: data.get(name, "") for name in fields}


def billing_address(data):
    fields = ("first_name", "last_name", "street", "postal_code", "city", "country")
    prefix = "billing_" if data.get("billing_separate") else ""
    return {name: data.get(prefix + name, "") for name in fields}
