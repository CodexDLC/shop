import re

from django import forms

from web.localization import translate_text
from web.shop.identity import PUBLIC_FIELDS
from web.shop.models import StoreIdentity


class StoreIdentityForm(forms.ModelForm):
    state = forms.CharField(widget=forms.HiddenInput)

    class Meta:
        model = StoreIdentity
        fields = PUBLIC_FIELDS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != "state":
                field.label = translate_text(f"staff.store_identity.field.{name}")
                field.widget.attrs.update({"class": "form-control"})
        self.fields["country"].widget = forms.Select(choices=[("DE", translate_text("staff.store_identity.germany"))], attrs={"class": "form-select"})

    def clean_country(self):
        value = self.cleaned_data["country"].upper()
        if value != "DE":
            raise forms.ValidationError(translate_text("staff.store_identity.country_error"))
        return value

    def clean_postal_code(self):
        value = self.cleaned_data["postal_code"]
        if not re.fullmatch(r"[0-9]{5}", value):
            raise forms.ValidationError(translate_text("staff.store_identity.postal_error"))
        return value

    def clean_contact_phone(self):
        value = self.cleaned_data["contact_phone"]
        normalized = re.sub(r"[ ()/.-]", "", value)
        if value and not re.fullmatch(r"\+?[0-9]{3,20}", normalized):
            raise forms.ValidationError(translate_text("staff.store_identity.phone_error"))
        return value
