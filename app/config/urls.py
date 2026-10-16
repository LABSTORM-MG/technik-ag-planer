from django.conf import settings
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Technik-AG Planer – Betreiber"
admin.site.site_title = "Technik-AG Planer"
admin.site.index_title = "Verwaltung"

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("", include("apps.core.urls")),
]
