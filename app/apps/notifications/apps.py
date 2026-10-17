from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    name = "apps.notifications"
    verbose_name = "Benachrichtigungen"

    def ready(self):
        from . import signals

        signals.connect()
