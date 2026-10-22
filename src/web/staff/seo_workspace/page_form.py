from django import forms

from web.localization import translate_text


class SeoPageForm(forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)

    def __init__(self, *args, user, page, **kwargs):
        super().__init__(*args, initial={"version": page["version"], **{
            field: page[field] for field in ("title", "description", "body")}}, **kwargs)
        for name, permission, limit in [("title", "change_metadata", 160),
                                        ("description", "change_metadata", 320),
                                        ("body", "change_text", 10000)]:
            if user.has_perm(f"seo.{permission}") and (name != "body" or page.get("body_allowed", True)):
                self.fields[name] = forms.CharField(
                    required=False, max_length=limit, label=translate_text(f"staff.seo.field.{name}"),
                    widget=(forms.TextInput(attrs={"class": "form-control"}) if name == "title" else
                            forms.Textarea(attrs={"class": "form-control", "rows": 8 if name == "body" else 2})),
                )
