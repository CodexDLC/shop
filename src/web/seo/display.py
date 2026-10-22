from django.conf import settings
from django.utils.html import strip_tags


def display_title(value):
    value = strip_tags(value)
    site = settings.SEO_SITE_NAME
    return value if value.endswith(site) else f"{value} | {site}"


def display_metadata(values):
    return {**values, "title": display_title(values["title"]), "description": strip_tags(values["description"])[:300]}
