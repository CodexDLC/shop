"""Small literal template language. No attribute access, evaluation or HTML."""
import re

from django.core.exceptions import ValidationError

VARIABLES = {"name", "brand", "category", "site"}
TOKEN = re.compile(r"\{([a-z]+)\}")


def validate_template(value):
    if len(value) > 320:
        raise ValidationError("SEO template is too long.")
    if "<" in value or ">" in value or any(ord(char) < 32 for char in value):
        raise ValidationError("Use plain text only.")
    tokens = TOKEN.findall(value)
    if any(token not in VARIABLES for token in tokens) or "{" in TOKEN.sub("", value) or "}" in TOKEN.sub("", value):
        raise ValidationError("Allowed variables: {name}, {brand}, {category}, {site}.")
    return value


def render_template(value, variables):
    validate_template(value)
    return TOKEN.sub(lambda match: str(variables.get(match.group(1), "")), value).strip()
