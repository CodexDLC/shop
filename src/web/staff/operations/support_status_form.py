from django import forms
from django.utils.functional import lazy

from web.localization import translate_text

text = lazy(translate_text, str)


class SupportStatusForm(forms.Form):
    original_state = forms.CharField(widget=forms.HiddenInput)
    action = forms.ChoiceField(choices=[("resolve", "resolve"), ("reopen", "reopen")], widget=forms.HiddenInput)
