from django import forms
from django.contrib.auth import get_user_model

from web.localization import translate_text


class ProfileForm(forms.ModelForm):
    display_name = forms.CharField(max_length=150, strip=True)

    class Meta:
        model = get_user_model()
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["display_name"].label = translate_text("customer.account.profile.name")
        if not self.is_bound:
            self.initial["display_name"] = self.instance.get_full_name()

    def clean_display_name(self):
        name = self.cleaned_data["display_name"]
        if any(ord(char) < 32 or ord(char) == 127 for char in name):
            raise forms.ValidationError(translate_text("customer.account.profile.invalid_name"))
        return name

    def save(self, commit=True):
        self.instance.first_name = self.cleaned_data["display_name"]
        self.instance.last_name = ""
        if commit:
            self.instance.save(update_fields=["first_name", "last_name"])
        return self.instance
