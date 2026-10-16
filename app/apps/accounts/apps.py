from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "apps.accounts"
    verbose_name = "Konten"

    def ready(self):
        from apps.audit.registry import register

        register(
            self.get_model("User"),
            exclude=["password", "last_login"],
            organization=None,
        )
