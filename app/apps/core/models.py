from django.db import models


class LegalPage(models.Model):
    """Impressum, Datenschutzerklärung, Nutzungsbedingungen – trägt der Betreiber im Django-Admin
    ein (Vorlagen: docs/rechtliches/). Gilt für die ganze Installation, nicht je AG."""

    class Kind(models.TextChoices):
        IMPRINT = "impressum", "Impressum"
        PRIVACY = "datenschutz", "Datenschutzerklärung"
        TERMS = "nutzungsbedingungen", "Nutzungsbedingungen"

    kind = models.CharField("Seite", max_length=30, choices=Kind.choices, unique=True)
    content = models.TextField(
        "Text",
        help_text="Absätze durch Leerzeilen trennen; Links und E-Mail-Adressen werden "
        "automatisch anklickbar.",
    )
    updated_at = models.DateTimeField("zuletzt geändert", auto_now=True)

    class Meta:
        verbose_name = "Rechtstext"
        verbose_name_plural = "Rechtstexte"
        ordering = ["kind"]

    def __str__(self):
        return self.get_kind_display()
