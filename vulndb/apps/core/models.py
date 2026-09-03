from __future__ import annotations

from django.db import models


class SystemSettings(models.Model):
    """Singleton application settings."""

    setup_completed = models.BooleanField(default=False)
    setup_step = models.PositiveSmallIntegerField(default=1)

    organization_name = models.CharField(max_length=255, blank=True, default="")
    local_id_prefix = models.CharField(max_length=16, blank=True, default="ACME")

    product_name = models.CharField(max_length=64, default="VULNDB")
    login_title = models.CharField(
        max_length=255,
        blank=True,
        default="Управление уязвимостями в одном контуре",
    )
    login_text = models.TextField(
        blank=True,
        default=(
            "Каталог NVD / KEV / БДУ, локальные уязвимости с вашим префиксом ID, "
            "заявки на устранение и контроль лицензии."
        ),
    )
    logo = models.ImageField(upload_to="branding/", blank=True, null=True)

    # Sync sources
    nvd_api_key = models.CharField(max_length=255, blank=True, default="")
    nvd_enabled = models.BooleanField(default=True)
    kev_enabled = models.BooleanField(default=True)
    bdu_enabled = models.BooleanField(default=True)
    sync_cron_hint = models.CharField(max_length=64, blank=True, default="hourly")

    # Mail
    smtp_host = models.CharField(max_length=255, blank=True, default="")
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_user = models.CharField(max_length=255, blank=True, default="")
    smtp_password = models.CharField(max_length=255, blank=True, default="")
    smtp_use_tls = models.BooleanField(default=True)
    smtp_from = models.CharField(max_length=255, blank=True, default="")

    # Telegram
    telegram_bot_token = models.CharField(max_length=255, blank=True, default="")
    telegram_chat_id = models.CharField(max_length=64, blank=True, default="")
    telegram_enabled = models.BooleanField(default=False)

    # DB meta (password stored in .env, not here)
    db_host = models.CharField(max_length=255, blank=True, default="127.0.0.1")
    db_port = models.PositiveIntegerField(default=5432)
    db_name = models.CharField(max_length=128, blank=True, default="vulndb")
    db_user = models.CharField(max_length=128, blank=True, default="vulndb")
    db_sslmode = models.CharField(max_length=16, blank=True, default="prefer")
    db_configured = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Системные настройки"
        verbose_name_plural = "Системные настройки"

    def __str__(self) -> str:
        return "SystemSettings"

    @classmethod
    def load(cls) -> "SystemSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


RESERVED_PREFIXES = frozenset({"CVE", "BDU"})
