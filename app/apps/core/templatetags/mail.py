"""Hilfen für E-Mail-Vorlagen (ADR 0026).

Mail-Programme kennen keine CSS-Variablen. Die Vorlagen holen ihre Farben deshalb beim Rendern
aus `tokens.css`; so bleibt die Datei die einzige Stelle mit Farbwerten.
"""

import re
from functools import lru_cache

from django import template
from django.conf import settings
from django.urls import reverse

register = template.Library()

TOKEN = re.compile(r"--([\w-]+):\s*([^;]+);")


@lru_cache(maxsize=1)
def _tokens():
    css = (settings.BASE_DIR / "static" / "css" / "tokens.css").read_text()
    return {name: value.strip() for name, value in TOKEN.findall(css)}


@register.simple_tag
def token(name):
    """Wert eines Design-Tokens, z. B. `{% token "color-primary" %}`."""
    return _tokens()[name]


@register.simple_tag
def site_url(url_name):
    """Absoluter Link auf eine Seite der App."""
    return settings.SITE_URL.rstrip("/") + reverse(url_name)
