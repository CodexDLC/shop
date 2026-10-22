from django import template

from ..navigation import header_section_visibility

register = template.Library()
register.simple_tag(header_section_visibility)
