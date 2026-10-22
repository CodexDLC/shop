import re
from decimal import Decimal

from django import forms
from django.utils.functional import lazy

from web.cart.models import PromoCode
from web.localization import translate_text

text = lazy(translate_text, str)


class PromoForm(forms.ModelForm):
    original_state = forms.CharField(widget=forms.HiddenInput)

    class Meta:
        model = PromoCode
        fields = ("code", "kind", "value", "min_subtotal", "currency", "is_active", "starts_at", "ends_at")
        labels = {name: text(f"staff.records.form.{name}") for name in fields}
        widgets = {
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["kind"].choices = [("percent", text("staff.records.kind.percent")),
                                         ("fixed", text("staff.records.kind.fixed"))]
        for name, item in self.fields.items():
            item.widget.attrs["class"] = "form-check-input" if name == "is_active" else "form-control"
            item.error_messages.update({code: text("staff.records.promo_error.required") for code in ("required",)})
            item.error_messages.update({code: text("staff.records.promo_error.number") for code in (
                "invalid", "invalid_choice", "max_length", "max_digits", "max_decimal_places",
                "max_whole_digits", "unique", "min_value", "max_value",
            )})

    def clean_currency(self):
        value = self.cleaned_data["currency"]
        if value != "EUR":
            raise forms.ValidationError(text("staff.records.promo_error.currency"), code="currency")
        return value

    def _post_clean(self):
        # Run normal ModelForm/model/constraint/unique validation before adapting feedback.
        super()._post_clean()
        if not self._errors:
            return
        obj = self.instance
        reasons = {}
        value = obj.value
        if isinstance(value, Decimal) and value.is_finite():
            if obj.kind == "percent" and not 0 < value <= 100:
                reasons["value"] = "percent"
            elif value <= 0:
                reasons["value"] = "positive"
        if isinstance(obj.min_subtotal, Decimal) and obj.min_subtotal < 0:
            reasons["min_subtotal"] = "minimum"
        if obj.code and not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{0,31}", obj.code):
            reasons["code"] = "code"
        if obj.starts_at and obj.ends_at and obj.ends_at <= obj.starts_at:
            reasons["ends_at"] = "date_order"
        constraints = {
            "promo_value_positive": "value", "promo_kind_value_valid": "value",
            "promo_minimum_nonnegative": "min_subtotal", "promo_code_ascii_upper": "code",
            "promo_dates_ordered": "ends_at", "promo_currency_eur": "currency",
        }
        normalized = []
        for name, errors in self._errors.items():
            for error in errors.as_data():
                target = name if name != "__all__" else None
                message = str(error.message)
                constraint = next((field for constraint, field in constraints.items() if constraint in message), None)
                if constraint:
                    target = constraint
                    key = reasons.get(target, "currency" if target == "currency" else "invalid")
                elif target is None and message == "commerce.error.coupon_invalid":
                    # The model's general error accompanies precise field/constraint failures.
                    if reasons or any(field != "__all__" for field in self._errors):
                        continue
                    key = "invalid"
                elif target == "code" and error.code == "unique":
                    key = "duplicate"
                elif error.code == "required":
                    key = "required"
                elif target in reasons:
                    key = reasons[target]
                elif target == "code":
                    key = "code"
                elif target == "currency":
                    key = "currency"
                elif target in ("starts_at", "ends_at"):
                    key = "date"
                elif target == "kind":
                    key = "kind"
                else:
                    key = "number" if target in ("value", "min_subtotal") else "invalid"
                normalized.append((target, key))
        normalized.extend(reasons.items())
        self._errors.clear()
        for target, key in dict.fromkeys(normalized):
            self.add_error(target, translate_text(f"staff.records.promo_error.{key}"))
