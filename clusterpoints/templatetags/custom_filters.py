# clusterpoints/templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, '')

@register.filter
def abs(value):
    try:
        v = float(value)
        return v if v >= 0 else -v
    except (TypeError, ValueError):
        return value

@register.filter
def split(value, delimiter=','):
    return [s.strip() for s in value.split(delimiter)]