from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("vulndb.apps.accounts.urls")),
    path("setup/", include("vulndb.apps.core.urls_setup")),
    path("settings/", include("vulndb.apps.core.urls_settings")),
    path("vulns/", include("vulndb.apps.vulns.urls")),
    path("tickets/", include("vulndb.apps.tickets.urls")),
    path("", include("vulndb.apps.core.urls")),
    path("", include("vulndb.apps.licensing.urls")),
]
