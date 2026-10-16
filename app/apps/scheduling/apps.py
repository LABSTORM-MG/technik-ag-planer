from django.apps import AppConfig


class SchedulingConfig(AppConfig):
    name = "apps.scheduling"
    verbose_name = "Termine und Zeiten"

    def ready(self):
        from apps.audit.registry import register as audit
        from apps.organizations import export

        for name in ["SchoolPeriod", "EventSeries", "Event", "EventAttendee", "Unavailability"]:
            model = self.get_model(name)
            audit(model)
            export.register(model)
