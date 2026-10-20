import re

from django import forms


class CheckoutAddressForm(forms.Form):
    email = forms.EmailField(max_length=254)
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    street = forms.CharField(max_length=200)
    postal_code = forms.RegexField(r"^[0-9]{5}$", max_length=5)
    city = forms.CharField(max_length=100)
    country = forms.ChoiceField(choices=[("DE", "Deutschland")])

    def clean(self):
        cleaned = super().clean()
        for name in ("first_name", "last_name", "street", "city"):
            value = cleaned.get(name, "")
            if any(ord(char) < 32 for char in value):
                self.add_error(name, "commerce.error.address")
        for name in ("first_name", "last_name", "city"):
            if name in cleaned and not any(char.isalpha() for char in cleaned[name]):
                self.add_error(name, "commerce.error.address")
        if "street" in cleaned and not (re.search(r"[0-9]", cleaned["street"])
                                         and any(char.isalpha() for char in cleaned["street"])):
            self.add_error("street", "commerce.error.address")
        return cleaned
