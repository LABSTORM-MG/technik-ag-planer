from django.contrib import admin

from .models import AuditEntry


@admin.register(AuditEntry)
class AuditEntryAdmin(admin.ModelAdmin):
    list_display = [
        "created_at",
        "actor_label",
        "organization_label",
        "action",
        "object_type",
        "object_repr",
    ]
    list_filter = ["action", "object_type", "organization"]
    search_fields = ["actor_label", "organization_label", "object_repr", "object_id"]
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
