# Native
import json

# Django
from django import template
from django.utils.safestring import mark_safe

# Create a custom template filter library
register = template.Library()


# Safely access dictionary values in templates
@register.filter
def get_item(d, key):
    if isinstance(d, dict):
        return d.get(key)
    return None


@register.filter
def json_escape(value):
    # Convert Python data to a JSON string safe for inline <script> usage.
    json_str = json.dumps(value)
    safe_str = json_str.replace("</", "<\\/")  # prevent </script> injection
    return mark_safe(safe_str)  # nosec B703,B308
