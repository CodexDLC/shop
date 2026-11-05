from django import forms

from web.localization import translate_text

from .intents import MAX_INT


class StockForm(forms.Form):
    intent = forms.CharField(widget=forms.HiddenInput, max_length=2000)
    quantity = forms.IntegerField(min_value=0, max_value=MAX_INT,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'inputmode': 'numeric'}))
    reason = forms.CharField(max_length=500, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))

    def __init__(self, *args, action, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['quantity'].label = translate_text('staff.inventory.quantity.' + action)
        self.fields['reason'].label = translate_text('staff.inventory.reason')
        self.fields['reason'].help_text = translate_text('staff.inventory.reason_help')
        if action == 'receive':
            self.fields['quantity'].min_value = 1
            self.fields['quantity'].widget.attrs['min'] = 1
        if action == 'adjust':
            self.fields['quantity'].widget.attrs['x-model'] = 'after'

    def clean_quantity(self):
        value = self.cleaned_data['quantity']
        if self.fields['quantity'].min_value == 1 and value < 1:
            raise forms.ValidationError(translate_text('staff.inventory.error.invalid_quantity'))
        return value
