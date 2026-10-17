from django.apps import AppConfig
from django.db.models.signals import post_save, pre_save


class BoardConfig(AppConfig):
    name = "apps.board"
    verbose_name = "Board"

    def ready(self):
        from apps.audit.registry import register as audit
        from apps.organizations import export
        from apps.organizations.models import Membership
        from apps.productions.models import Production

        from . import signals

        pre_save.connect(signals.remember_production, sender=Production, dispatch_uid="board-pre")
        post_save.connect(
            signals.announce_production, sender=Production, dispatch_uid="board-production"
        )
        post_save.connect(signals.announce_member, sender=Membership, dispatch_uid="board-member")

        message = self.get_model("Message")
        audit(message)
        export.register(message)
        export.register(self.get_model("ReadMarker"))
