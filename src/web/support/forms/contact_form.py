from django import forms

from web.localization import translate_text


class ContactForm(forms.Form):
    name = forms.CharField(max_length=120)
    email = forms.EmailField(max_length=254)
    topic = forms.ChoiceField(choices=[(key, key) for key in (
        "retoure", "versand", "groesse", "zahlung", "reklamation", "sonstiges",
    )])
    message = forms.CharField(max_length=4000, widget=forms.Textarea)
    website = forms.CharField(required=False, max_length=200, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, key in {"name": "18a493008ffa", "email": "ce8fdbcbfea8",
                          "topic": "177549c4e26c", "message": "816c03d4877e"}.items():
            self.fields[name].label = translate_text(f"support.help.text.{key}")

    def clean_website(self):
        value = self.cleaned_data.get("website")
        if value:
            raise forms.ValidationError(translate_text("support.help.ui.contact_rejected"))
        return ""
