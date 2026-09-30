"""
Project-wide template filters, registered as a template builtin in settings
(no ``{% load %}`` needed).
"""
import json

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

# Same escapes Django's json_script uses: inside a JSON document these
# characters can only appear in string literals, where \uXXXX is equivalent,
# so the output stays valid JS but can never close a <script> tag.
_JS_ESCAPES = {ord('<'): '\\u003C', ord('>'): '\\u003E', ord('&'): '\\u0026'}


@register.filter(is_safe=True)
def js_json(value):
    """
    Emit data inline inside <script> without XSS risk.

    Accepts either a pre-serialised JSON string (what the views pass today)
    or a plain Python value. Use instead of ``{{ some_json|safe }}``.
    """
    if value is None:
        return mark_safe('null')
    if not isinstance(value, str):
        value = json.dumps(value, default=str)
    return mark_safe(value.translate(_JS_ESCAPES))
