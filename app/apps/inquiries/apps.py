from django.apps import AppConfig


class InquiriesConfig(AppConfig):
    name = "apps.inquiries"
    verbose_name = "Technik-Anfragen"

    def ready(self):
        from apps.audit.registry import register as audit
        from apps.organizations import export

        for name in ["InquiryLink", "Inquiry"]:
            model = self.get_model(name)
            audit(model)
            export.register(model)
