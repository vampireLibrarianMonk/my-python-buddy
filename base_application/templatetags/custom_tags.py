from django import template

register = template.Library()


@register.filter
def get_item(d, key):
    """Safe dictionary lookup in templates (dict[key])."""
    if isinstance(d, dict):
        return d.get(key)
    return None
