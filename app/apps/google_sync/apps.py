from django.apps import AppConfig


class GoogleSyncConfig(AppConfig):
    name = "apps.google_sync"
    verbose_name = "Google-Anbindung"

    def ready(self):
        from apps.audit.registry import register as audit
        from apps.organizations import export

        from . import signals  # noqa: F401 – Kalender-Abgleich nach Änderungen

        connection = self.get_model("GoogleConnection")
        audit(connection, exclude=["refresh_token_encrypted"])
        export.register(connection, exclude={"refresh_token_encrypted"})
        # Übertragene Termine nur exportieren – jeder Abgleich würde sonst das Protokoll füllen
        export.register(self.get_model("SyncedEvent"))
        attachment = self.get_model("Attachment")
        audit(attachment)
        export.register(attachment)
