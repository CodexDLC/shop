from django import forms

from web.localization import translate_text

from .intents import MAX_INT


class FilterForm(forms.Form):
    q = forms.CharField(required=False, max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'type': 'search'}))
    status = forms.ChoiceField(required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    threshold = forms.IntegerField(required=False, min_value=0, max_value=MAX_INT,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'inputmode': 'numeric'}))

    def __init__(self, *args, balance=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['q'].label = translate_text('staff.records.search')
        self.fields['status'].label = translate_text('staff.inventory.filter')
        self.fields['status'].choices = [(value, translate_text('staff.inventory.filter.' + (value or 'all')))
            for value in ('', 'missing', 'unavailable', 'reserved', 'low')]
        self.fields['threshold'].label = translate_text('staff.inventory.threshold')
        if not balance:
            del self.fields['status']
            del self.fields['threshold']

    def clean(self):
        data = super().clean()
        if data.get('status') == 'low' and data.get('threshold') is None:
            self.add_error('threshold', translate_text('staff.inventory.threshold_required'))
        return data
