from django.apps import AppConfig
from django.db.models.signals import post_save


def _create_defaults(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        from .models import ensure_defaults

        ensure_defaults(instance)


class ProductionsConfig(AppConfig):
    name = "apps.productions"
    verbose_name = "Produktionen"

    def ready(self):
        from apps.audit.registry import register as audit
        from apps.organizations import export
        from apps.organizations.models import Organization

        post_save.connect(_create_defaults, sender=Organization, dispatch_uid="production-defaults")

        for name in ["Category", "ProductionStatus", "Production", "Job", "CrewAssignment", "Todo"]:
            model = self.get_model(name)
            audit(model)
            export.register(model)
