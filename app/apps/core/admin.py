from django.contrib import admin

from .models import LegalPage


@admin.register(LegalPage)
class LegalPageAdmin(admin.ModelAdmin):
    list_display = ["kind", "updated_at"]
