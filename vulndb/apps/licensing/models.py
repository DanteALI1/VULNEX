from django.db import models


class LicenseState(models.Model):
    license_id = models.CharField(max_length=128, blank=True, default="")
    customer = models.CharField(max_length=255, blank=True, default="")
    fingerprint_expected = models.CharField(max_length=128, blank=True, default="")
    raw_license = models.JSONField(default=dict, blank=True)
    valid = models.BooleanField(default=False)
    in_grace = models.BooleanField(default=False)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    last_heartbeat_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Состояние лицензии"

    def __str__(self) -> str:
        return self.license_id or "LicenseState"
