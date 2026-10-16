import re

from django import forms

from web.customer.models import CustomerAddress
from web.localization import translate_text


class CustomerAddressForm(forms.ModelForm):
    class Meta:
        model = CustomerAddress
        fields = ["kind", "recipient", "street_address", "post_number", "station_number", "postal_code",
                  "city", "country", "is_default"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["country"].required = False
        if not self.instance.pk:
            self.initial.setdefault("kind", "standard")
        for name, field in self.fields.items():
            field.label = translate_text(f"customer.account.address.{name}")

    def clean(self):
        cleaned = super().clean()
        for name in ("recipient", "city", "street_address"):
            value = cleaned.get(name, "")
            if value and (not any(char.isalpha() for char in value)
                          or any(ord(char) < 32 for char in value)):
                self.add_error(name, translate_text("customer.account.address.error.text"))
        if not re.fullmatch(r"[0-9]{5}", cleaned.get("postal_code", "")):
            self.add_error("postal_code", translate_text("customer.account.address.error.postal_code"))
        cleaned["country"] = cleaned.get("country") or "DE"
        if cleaned.get("kind") == "standard":
            street = cleaned.get("street_address", "")
            if not street or not re.search(r"[0-9]", street) or not any(c.isalpha() for c in street):
                self.add_error("street_address", translate_text("customer.account.address.error.street_address"))
            cleaned["post_number"] = ""
            cleaned["station_number"] = ""
        elif cleaned.get("kind") == "packstation":
            if not re.fullmatch(r"[0-9]{6,10}", cleaned.get("post_number", "")):
                self.add_error("post_number", translate_text("customer.account.address.error.post_number"))
            if not re.fullmatch(r"[0-9]{1,5}", cleaned.get("station_number", "")):
                self.add_error("station_number", translate_text("customer.account.address.error.station_number"))
            cleaned["street_address"] = ""
        return cleaned
