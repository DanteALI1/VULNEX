from django.contrib import admin

from .models import LicenseState


@admin.register(LicenseState)
class LicenseStateAdmin(admin.ModelAdmin):
    list_display = ("license_id", "customer", "valid", "in_grace", "last_verified_at")
