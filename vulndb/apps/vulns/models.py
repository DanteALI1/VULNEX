from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class Vulnerability(models.Model):
    class RecordType(models.TextChoices):
        CVE = "cve", "CVE"
        BDU = "bdu", "BDU"
        LOCAL = "local", "LOCAL"

    vuln_id = models.CharField(max_length=64, unique=True, db_index=True)
    record_type = models.CharField(max_length=16, choices=RecordType.choices, default=RecordType.CVE)
    title = models.TextField(blank=True, default="")
    description_nvd = models.TextField(blank=True, default="")
    description_bdu = models.TextField(blank=True, default="")

    severity = models.CharField(max_length=16, blank=True, default="")
    cvss_score = models.FloatField(null=True, blank=True)
    cvss_v31 = models.JSONField(default=dict, blank=True)
    cvss_v30 = models.JSONField(default=dict, blank=True)
    cvss_v2 = models.JSONField(default=dict, blank=True)
    cvss_v40 = models.JSONField(default=dict, blank=True)

    cwe = models.JSONField(default=list, blank=True)
    cpe = models.JSONField(default=list, blank=True)
    references = models.JSONField(default=list, blank=True)

    in_kev = models.BooleanField(default=False, db_index=True)
    kev_data = models.JSONField(default=dict, blank=True)
    bdu_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    has_bdu = models.BooleanField(default=False)
    bdu_raw = models.JSONField(default=dict, blank=True)
    vendor = models.TextField(blank=True, default="")
    product_name = models.TextField(blank=True, default="")
    product_version = models.TextField(blank=True, default="")
    remediation = models.TextField(blank=True, default="")
    vuln_status = models.TextField(blank=True, default="")
    exploit_present = models.TextField(blank=True, default="")

    published_at = models.DateTimeField(null=True, blank=True)
    modified_at = models.DateTimeField(null=True, blank=True)
    raw_nvd = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-modified_at", "-created_at"]
        verbose_name = "Уязвимость"
        verbose_name_plural = "Уязвимости"

    def __str__(self) -> str:
        return self.vuln_id

    @property
    def badges(self) -> list[str]:
        out = []
        if self.in_kev:
            out.append("KEV")
        if self.has_bdu or self.bdu_id:
            out.append("BDU")
        if self.record_type == self.RecordType.LOCAL:
            out.append("LOCAL")
        return out


class LocalIdSequence(models.Model):
    prefix = models.CharField(max_length=16)
    year = models.PositiveIntegerField()
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("prefix", "year")

    @classmethod
    def next_id(cls, prefix: str) -> str:
        year = timezone.now().year
        prefix = prefix.upper()
        seq, _ = cls.objects.select_for_update().get_or_create(prefix=prefix, year=year)
        seq.last_number += 1
        seq.save(update_fields=["last_number"])
        return f"{prefix}-{year}-{seq.last_number:04d}"


class SyncState(models.Model):
    class Source(models.TextChoices):
        NVD = "nvd", "NVD"
        KEV = "kev", "CISA KEV"
        BDU = "bdu", "БДУ ФСТЭК"

    source = models.CharField(max_length=16, choices=Source.choices, unique=True)
    status = models.CharField(max_length=32, default="idle")
    checkpoint = models.CharField(max_length=255, blank=True, default="")
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    items_total = models.PositiveIntegerField(default=0)
    items_synced = models.PositiveIntegerField(default=0)
    meta = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return f"{self.source}: {self.status}"
