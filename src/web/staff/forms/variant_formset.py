from django import forms
from django.forms.formsets import BaseFormSet

from web.catalog.models import ProductVariant
from web.localization.translation import translate_text


class VariantFormSet(BaseFormSet):
    def __init__(self, *args, expected_ids=(), can_add=False, requires_active=False, **kwargs):
        self.expected_ids = list(expected_ids)
        self.can_add = can_add
        self.requires_active = requires_active
        super().__init__(*args, **kwargs)

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        existing_ids = [form.cleaned_data.get("id") for form in self.forms[:len(self.expected_ids)]]
        if self.initial_form_count() != len(self.expected_ids) or existing_ids != self.expected_ids:
            raise forms.ValidationError(translate_text("staff.variants.invalid_rows"))
        rows = [form.cleaned_data for form in self.forms if form.cleaned_data]
        if any(row.get("id") for row in rows[len(self.expected_ids):]):
            raise forms.ValidationError(translate_text("staff.variants.invalid_rows"))
        if len(rows) > len(self.expected_ids) and not self.can_add:
            raise forms.ValidationError(translate_text("staff.variants.add_denied"))
        skus = [row["sku"] for row in rows]
        combinations = [(row["color_code"], row["size"]) for row in rows]
        if len(skus) != len(set(skus)) or len(combinations) != len(set(combinations)):
            raise forms.ValidationError(translate_text("staff.variants.duplicate"))
        if len({row["currency"] for row in rows}) > 1:
            raise forms.ValidationError(translate_text("staff.variants.mixed_currency"))
        if self.requires_active and not any(row["is_active"] for row in rows):
            raise forms.ValidationError(translate_text("staff.product_form.active_without_variants"))
        if ProductVariant.objects.filter(sku__in=skus).exclude(pk__in=self.expected_ids).exists():
            raise forms.ValidationError(translate_text("staff.variants.duplicate"))
