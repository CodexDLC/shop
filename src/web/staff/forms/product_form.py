import hashlib
import json
import re

from django import forms
from django.core import signing
from django.utils.functional import lazy

from web.catalog.models import Product
from web.localization.translation import translate_text

text = lazy(translate_text, str)
SIGNING_SALT = "staff.product.edit.v1"


def product_snapshot(product):
    """Fingerprint editable state and tags; callers lock the product before saving."""
    state = {
        "pk": product.pk,
        "brand": product.brand_id,
        "category": product.category_id,
        "model_name": product.model_name,
        "manufacturer_article": product.manufacturer_article,
        "slug": product.slug,
        "description_key": product.description_key,
        "is_active": product.is_active,
        "new_until": product.new_until.isoformat() if product.new_until else None,
        "tags": sorted(product.tags.values_list("pk", flat=True)) if product.pk else [],
    }
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()


class ProductForm(forms.ModelForm):
    original_state = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Product
        fields = [
            "brand", "category", "model_name", "manufacturer_article", "slug", "description_key", "tags", "is_active", "new_until",
        ]
        labels = {name: text(f"staff.product_form.{name}") for name in fields}
        help_texts = {
            "slug": text("staff.product_form.slug_help"),
            "description_key": text("staff.product_form.description_key_help"),
            "is_active": text("staff.product_form.publication_help"),
            "new_until": text("staff.product_form.new_until_help"),
        }
        error_messages = {
            name: {
                "required": text("staff.product_form.required"),
                "invalid": text("staff.product_form.invalid"),
                "invalid_choice": text("staff.product_form.invalid_choice"),
                "invalid_pk_value": text("staff.product_form.invalid_choice"),
                "max_length": text("staff.product_form.too_long"),
                "unique": text("staff.product_form.slug_taken"),
            }
            for name in fields
        }
        widgets = {"tags": forms.SelectMultiple(attrs={"size": 5}),
                   "new_until": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["is_active"].disabled = True
        if not self.instance.pk:
            self.instance.is_active = False
            self.initial["is_active"] = False
        self.current_snapshot = product_snapshot(self.instance)
        if self.instance.pk:
            self.initial["original_state"] = signing.dumps(
                {"pk": self.instance.pk, "snapshot": self.current_snapshot}, salt=SIGNING_SALT,
            )
        for field in self.fields.values():
            if isinstance(field.widget, forms.HiddenInput):
                continue
            field.widget.attrs["class"] = (
                "form-check-input" if isinstance(field.widget, forms.CheckboxInput)
                else "form-select" if isinstance(field.widget, forms.Select)
                else "form-control"
            )

    def clean_description_key(self):
        value = self.cleaned_data["description_key"]
        if value and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", value):
            raise forms.ValidationError(text("staff.product_form.invalid_key"), code="invalid_key")
        return value

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk:
            try:
                original = signing.loads(cleaned.get("original_state", ""), salt=SIGNING_SALT, max_age=7200)
            except signing.BadSignature:
                raise forms.ValidationError(text("staff.product_form.invalid_state"), code="invalid_state") from None
            if not isinstance(original, dict) or original.get("pk") != self.instance.pk:
                raise forms.ValidationError(text("staff.product_form.invalid_state"), code="invalid_state")
            if original.get("snapshot") != self.current_snapshot:
                raise forms.ValidationError(text("staff.product_form.stale"), code="stale")
            if self.instance.is_active and not self.instance.variants.filter(is_active=True).exists():
                raise forms.ValidationError(text("staff.product_form.active_without_variants"), code="no_variants")
        return cleaned
