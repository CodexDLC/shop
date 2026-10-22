import re

from django import forms
from django.core import signing
from django.utils.functional import lazy

from web.catalog.models import Category, Product
from web.localization.translation import translate_text
from web.staff.catalog_workspace.category_tree import tree_rows
from web.staff.product_editing import content_fingerprint

text = lazy(translate_text, str)
SIGNING_SALT = "staff.product.edit.v1"


def product_snapshot(product):
    """Fingerprint editable state and tags; callers lock the product before saving."""
    return f'{product.publication_state}:{product.review_fingerprint}:{content_fingerprint(product)}'


class ProductForm(forms.ModelForm):
    original_state = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Product
        fields = [
            "brand", "category", "model_name", "manufacturer_article", "slug", "description_key", "tags", "materials", "properties", "is_active", "new_until",
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
        self.fields["category"].choices = [("", "---------"), *[
            (row["object"].pk, row["path"]) for row in tree_rows(list(Category.objects.order_by("position", "pk")))]]
        self.fields["is_active"].disabled = True
        self.fields["description_key"].disabled = True
        if not self.instance.pk:
            self.instance.is_active = False
            self.instance.editorial_state = "draft"
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
        return cleaned
