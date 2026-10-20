import re

from django import forms
from django.core.validators import RegexValidator

from web.localization.translation import translate_text


class VariantForm(forms.Form):
    id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    sku = forms.CharField(max_length=100)
    color_code = forms.CharField(max_length=40)
    color_name_key = forms.CharField(max_length=160)
    color_hex = forms.CharField(max_length=7, validators=[RegexValidator(r"^#[0-9a-fA-F]{6}$")])
    size = forms.CharField(max_length=20)
    price = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    currency = forms.CharField(max_length=3, validators=[RegexValidator(r"^[A-Z]{3}$")])
    demo_quantity = forms.IntegerField(min_value=0, max_value=2147483647)
    is_active = forms.BooleanField(required=False)
    is_on_sale = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.label = translate_text(f"staff.variants.{name}")
            field.widget.attrs["class"] = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
        if self.initial.get("id"):
            self.fields["sku"].disabled = True

    def clean_color_name_key(self):
        value = self.cleaned_data["color_name_key"]
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", value):
            raise forms.ValidationError(translate_text("staff.product_form.invalid_key"), code="invalid_key")
        return value
