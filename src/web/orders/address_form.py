import re

from django import forms


class CheckoutAddressForm(forms.Form):
    email = forms.EmailField(max_length=254)
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    street = forms.CharField(max_length=200, required=False)
    postal_code = forms.RegexField(r"^[0-9]{5}$", max_length=5)
    city = forms.CharField(max_length=100)
    country = forms.ChoiceField(choices=[("DE", "Deutschland")])
    shipping_type = forms.ChoiceField(choices=[("home", "Standard"), ("packstation", "Packstation")], required=False)
    post_number = forms.CharField(max_length=10, required=False)
    packstation_number = forms.CharField(max_length=3, required=False)
    billing_separate = forms.BooleanField(required=False)
    billing_first_name = forms.CharField(max_length=100, required=False)
    billing_last_name = forms.CharField(max_length=100, required=False)
    billing_street = forms.CharField(max_length=200, required=False)
    billing_postal_code = forms.CharField(max_length=5, required=False)
    billing_city = forms.CharField(max_length=100, required=False)
    billing_country = forms.CharField(max_length=2, required=False)

    def __init__(self, data=None, *args, **kwargs):
        if data is not None:
            data = data.copy()
            if data.get("shipping_type", "home") != "packstation":
                data["post_number"] = ""
                data["packstation_number"] = ""
            else:
                data["street"] = ""
            if str(data.get("billing_separate", "")).lower() in ("", "false", "0"):
                for name in self.base_fields:
                    if name.startswith("billing_") and name != "billing_separate":
                        data[name] = ""
        super().__init__(data, *args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        cleaned["shipping_type"] = cleaned.get("shipping_type") or "home"
        packstation = cleaned["shipping_type"] == "packstation"
        fields = ["first_name", "last_name", "city"]
        if packstation:
            for name, pattern in (("post_number", r"[0-9]{6,10}"), ("packstation_number", r"[0-9]{3}")):
                if not re.fullmatch(pattern, cleaned.get(name, "")):
                    self.add_error(name, "commerce.error.address")
            cleaned["street"] = "Packstation " + cleaned.get("packstation_number", "")
            if not cleaned.get("billing_separate"):
                self.add_error("billing_separate", "commerce.error.address")
        else:
            self._validate_street(cleaned, "street")
        if cleaned.get("billing_separate"):
            fields.extend(["billing_first_name", "billing_last_name", "billing_city"])
            self._validate_street(cleaned, "billing_street")
            if not re.fullmatch(r"[0-9]{5}", cleaned.get("billing_postal_code", "")):
                self.add_error("billing_postal_code", "commerce.error.address")
            if cleaned.get("billing_country") != "DE":
                self.add_error("billing_country", "commerce.error.address")
        for name in fields:
            value = cleaned.get(name, "")
            if not any(char.isalpha() for char in value) or any(ord(char) < 32 for char in value):
                self.add_error(name, "commerce.error.address")
        return cleaned

    def _validate_street(self, cleaned, name):
        value = cleaned.get(name, "")
        if (not re.search(r"[0-9]", value) or not any(char.isalpha() for char in value)
                or re.search(r"\bpackstation\b", value, re.IGNORECASE)
                or any(ord(char) < 32 for char in value)):
            self.add_error(name, "commerce.error.address")
