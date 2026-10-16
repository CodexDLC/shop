from codex_django.cabinet.quick_access import get_staff_quick_access_candidates
from django import forms


class QuickAccessForm(forms.Form):
    links = forms.MultipleChoiceField(required=False, widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["links"].choices = [
            (item["key"], f'{group["module_label"]} — {item["label"]}')
            for group in get_staff_quick_access_candidates() for item in group["items"]
            if not item["permissions"] or any(user.has_perm(p) for p in item["permissions"])
        ]
