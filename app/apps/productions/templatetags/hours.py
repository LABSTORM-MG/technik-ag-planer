from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def stunden(value):
    """Decimal → „3“, „6,5“ oder „2,75“ (ohne überflüssige Nullen)."""
    if value is None:
        return ""
    text = format(Decimal(value).quantize(Decimal("0.01")).normalize(), "f")
    return text.replace(".", ",")
