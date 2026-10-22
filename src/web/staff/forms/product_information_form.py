from django import forms
from django.utils.functional import lazy

from web.catalog.models import ProductInformation
from web.localization import translate_text

text = lazy(translate_text, str)


class ProductInformationForm(forms.ModelForm):
    original_state = forms.CharField(widget=forms.HiddenInput)

    class Meta:
        model = ProductInformation
        fields = ['description', 'composition', 'care', 'fit', 'origin', 'certification']
        labels = {name: text(f'staff.information.{name}') for name in fields}
        widgets = {name: forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}) for name in fields}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.error_messages.update(required=text('staff.product_form.required'),
                                        max_length=text('staff.product_form.too_long'))
