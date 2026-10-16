from django import template

from web.localization import translate_text

register = template.Library()


@register.simple_tag(name="text")
def text(key: str, **params: object) -> str:
    return translate_text(key, **params)
