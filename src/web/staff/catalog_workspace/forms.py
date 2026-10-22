from django import forms
from django.forms import inlineformset_factory, modelform_factory

from web.catalog.models import SizeGuide, SizeGuideRow
from web.localization.translation import translate_text

from .registry import RESOURCES


def decorate_form(form):
    for name, field in form.fields.items():
        field.label = translate_text(f"staff.workspace_catalog.field.{name}")
        field.widget.attrs["class"] = (
            "form-check-input" if isinstance(field.widget, forms.CheckboxInput)
            else "form-select" if isinstance(field.widget, forms.Select) else "form-control"
        )
        if name in ("name_key", "label_key"):
            field.disabled = True
            field.help_text = translate_text("staff.workspace_catalog.stable_key")
        if name == "is_published":
            field.help_text = translate_text("staff.workspace_catalog.publish_help")
        if name == "section":
            field.choices = [(key, translate_text(f"staff.workspace_catalog.section.{key}"))
                             for key in ("underwear", "swimwear", "other")]
    return form


def reference_form(resource, data=None, instance=None):
    model, _, fields = RESOURCES[resource]
    form_class = modelform_factory(model, fields=fields)
    form = decorate_form(form_class(data=data, instance=instance))
    if resource == "size_guides" and instance is not None and instance.pk:
        for name in ("brand", "category"):
            form.fields[name].disabled = True
            form.fields[name].help_text = translate_text("staff.workspace_catalog.binding_help")
    return form


def guide_rows(data=None, instance=None):
    factory = inlineformset_factory(
        SizeGuide, SizeGuideRow,
        fields=["size", "position", "waist_min_cm", "waist_max_cm", "hip_min_cm", "hip_max_cm"],
        extra=1, can_delete=False, max_num=100, validate_max=True, absolute_max=100,
    )
    formset = factory(data=data, instance=instance, prefix="rows")
    for form in formset.forms:
        decorate_form(form)
    return formset
