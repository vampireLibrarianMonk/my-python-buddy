from django import template

register = template.Library()


@register.filter
def get_latest_run(runs, analyzer_name):
    """
    Return the most recent run for a specific analyzer.
    Usage: {% with item.runs|get_latest_run:"bandit" as bandit_run %}
    """
    filtered = [r for r in runs.all() if r.analyzer == analyzer_name]
    return sorted(filtered, key=lambda r: r.started_at or r.created_at, reverse=True)[0] if filtered else None
