from django.conf import settings
from django.db import models


class AuditEntry(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    action = models.CharField(max_length=128)
    message = models.TextField(blank=True, default="")
    ip = models.GenericIPAddressField(null=True, blank=True)
    path = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Запись аудита"
        verbose_name_plural = "Журнал аудита"
