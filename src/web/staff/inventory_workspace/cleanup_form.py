from django import forms


class CleanupForm(forms.Form):
    intent = forms.CharField(widget=forms.HiddenInput, max_length=2000)
