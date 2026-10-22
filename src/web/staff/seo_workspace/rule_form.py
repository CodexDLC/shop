from django import forms

from web.localization import translate_text


class SeoRuleForm(forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    title_template = forms.CharField(max_length=160, required=False,
                                    widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}))
    description_template = forms.CharField(max_length=320, required=False,
                                          widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}))

    def __init__(self, *args, rule, **kwargs):
        super().__init__(*args, initial={field: rule[field] for field in self.base_fields}, **kwargs)
        for name in ("title_template", "description_template"):
            self.fields[name].label = translate_text(f"staff.seo.field.{name}")
