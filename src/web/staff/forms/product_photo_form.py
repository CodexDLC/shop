from django import forms
from django.utils.functional import lazy

from web.localization.translation import translate_text
from web.staff.photo_uploads import sanitize_photo

text = lazy(translate_text, str)


class ProductPhotoForm(forms.Form):
    color_code = forms.ChoiceField(required=False, label=text("staff.photos.color"))
    position = forms.IntegerField(min_value=0, max_value=99, label=text("staff.photos.position"))
    alt_text = forms.CharField(max_length=300, required=False, label=text("staff.photos.alt"))
    upload = forms.FileField(required=False, label=text("staff.photos.upload"),
                             widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}))

    def __init__(self, *args, product, image=None, color_codes=None, **kwargs):
        self.image = image
        kwargs.setdefault("auto_id", f"photo-{image.pk if image else 'new'}-%s")
        if image and "initial" not in kwargs:
            kwargs["initial"] = {"color_code": image.color_code, "position": image.position,
                                 "alt_text": image.alt_text}
        super().__init__(*args, **kwargs)
        if color_codes is None:
            color_codes = product.variants.order_by("color_code").values_list("color_code", flat=True).distinct()
        self.fields["color_code"].choices = [("", text("staff.photos.general"))] + [
            (code, code) for code in color_codes if code]
        self.fields["upload"].required = image is None
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"

    def clean_upload(self):
        upload = self.cleaned_data.get("upload")
        return sanitize_photo(upload) if upload else None
