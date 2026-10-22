from django import forms

from web.catalog.models import Category
from web.localization import translate_text
from web.staff.photo_uploads import sanitize_photo

from .category_tree import branch_ids, tree_rows


class CategoryForm(forms.ModelForm):
    upload = forms.FileField(required=False)
    remove_image = forms.BooleanField(required=False)
    confirm_visibility = forms.BooleanField(required=False)

    class Meta:
        model = Category
        fields = ["name_de", "name_ru", "slug", "parent", "section", "position", "is_visible",
                  "description_de", "description_ru", "seo_title", "seo_description", "image_alt"]
        widgets = {"description_de": forms.Textarea(attrs={"rows": 5}),
                   "description_ru": forms.Textarea(attrs={"rows": 4}),
                   "seo_description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, categories, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name_de"].required = True
        excluded = branch_ids(categories, self.instance.pk) if self.instance.pk else set()
        self.fields["parent"].choices = [("", translate_text("staff.categories.root")), *[
            (row["object"].pk, row["path"]) for row in tree_rows(categories) if row["object"].pk not in excluded]]
        if self.instance.pk:
            self.fields["slug"].disabled = True
            self.fields["slug"].help_text = translate_text("staff.categories.slug_help")
        for name, field in self.fields.items():
            field.label = translate_text(f"staff.categories.field.{name}")
            field.widget.attrs["class"] = (
                "form-check-input" if isinstance(field.widget, forms.CheckboxInput)
                else "form-select" if isinstance(field.widget, forms.Select) else "form-control")
        self.fields["section"].choices = [(key, translate_text(f"staff.workspace_catalog.section.{key}"))
                                          for key in ("underwear", "swimwear", "other")]
        self.fields["upload"].widget.attrs["accept"] = "image/jpeg,image/png,image/webp"

    def clean_upload(self):
        upload = self.cleaned_data.get("upload")
        return sanitize_photo(upload) if upload else None

    @property
    def field_groups(self):
        groups = [
            ("identity", ["name_de", "name_ru", "slug", "parent", "section"]),
            ("display", ["position", "is_visible", "confirm_visibility"]),
            ("image", ["upload", "remove_image", "image_alt"]),
            ("description", ["description_de", "description_ru"]),
            ("seo", ["seo_title", "seo_description"]),
        ]
        return [{"key": f"staff.categories.group.{name}", "fields": [self[field] for field in fields]}
                for name, fields in groups]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("upload") and cleaned.get("remove_image"):
            self.add_error("remove_image", translate_text("staff.categories.image_conflict"))
        return cleaned
