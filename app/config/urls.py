from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django_otp.admin import OTPAdminSite

# Der Django-Admin ist nur für den Betreiber – im Betrieb nur mit Zwei-Faktor-Anmeldung
if settings.ADMIN_REQUIRE_2FA:
    admin.site.__class__ = OTPAdminSite

admin.site.site_header = "Technik-AG Planer – Betreiber"
admin.site.site_title = "Technik-AG Planer"
admin.site.index_title = "Verwaltung"

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("", include("apps.accounts.urls")),
    path("", include("apps.organizations.urls")),
    path("", include("apps.productions.urls")),
    path("", include("apps.scheduling.urls")),
    path("", include("apps.board.urls")),
    path("", include("apps.inventory.urls")),
    path("", include("apps.core.urls")),
]
