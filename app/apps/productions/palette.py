"""Feste Farbpalette für Kategorien und Status. Die Farbwerte stehen in static/css/tokens.css
(--palette-<schlüssel>); hier nur Schlüssel und Namen."""

from django.db import models


class Color(models.TextChoices):
    GREEN = "green", "Grün"
    ORANGE = "orange", "Orange"
    BLUE = "blue", "Blau"
    LILAC = "lilac", "Flieder"
    RED = "red", "Rot"
    TEAL = "teal", "Türkis"
    PINK = "pink", "Pink"
    YELLOW = "yellow", "Gelb"
    VIOLET = "violet", "Violett"
    LIME = "lime", "Hellgrün"
    CORAL = "coral", "Koralle"
    GREY = "grey", "Grau"
