from django.contrib import admin

from .models import LocalIdSequence, SyncState, Vulnerability


@admin.register(Vulnerability)
class VulnerabilityAdmin(admin.ModelAdmin):
    list_display = ("vuln_id", "severity", "cvss_score", "in_kev", "has_bdu", "record_type")
    search_fields = ("vuln_id", "title", "bdu_id")
    list_filter = ("severity", "in_kev", "has_bdu", "record_type")


admin.site.register(SyncState)
admin.site.register(LocalIdSequence)
