from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    """PDFs: Call Sheets, Freistellungsliste, Packliste. Speichert selbst nichts."""

    name = "apps.documents"
    verbose_name = "Dokumente"
