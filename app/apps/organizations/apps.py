from django.apps import AppConfig


class OrganizationsConfig(AppConfig):
    name = "apps.organizations"
    verbose_name = "AGs und Mitglieder"

    def ready(self):
        from apps.audit.registry import register

        from . import export

        Organization = self.get_model("Organization")
        Membership = self.get_model("Membership")
        Invitation = self.get_model("Invitation")

        register(Organization, organization="self")
        register(Membership)
        register(Invitation, exclude=["token_hash"])

        export.register(Membership)
        export.register(Invitation, exclude=["token_hash"])
