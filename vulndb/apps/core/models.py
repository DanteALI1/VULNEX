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
    nvd_sync_interval_minutes = models.PositiveIntegerField(default=60)
    kev_enabled = models.BooleanField(default=True)
    kev_sync_interval_minutes = models.PositiveIntegerField(default=360)
    bdu_enabled = models.BooleanField(default=True)
    bdu_xlsx_url = models.URLField(
        blank=True,
        default="https://bdu.fstec.ru/files/documents/vullist.xlsx",
    )
    bdu_sync_interval_minutes = models.PositiveIntegerField(default=1440)
    bdu_verify_ssl = models.BooleanField(
        default=False,
        help_text="Сертификат ФСТЭК часто требует отключения verify в лаборатории",
    )
    sync_cron_hint = models.CharField(max_length=64, blank=True, default="custom")

    # Mail / Exchange
    mail_provider = models.CharField(
        max_length=32,
        default="smtp",
        help_text="smtp | exchange | office365 | gmail",
    )
    smtp_host = models.CharField(max_length=255, blank=True, default="")
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_user = models.CharField(max_length=255, blank=True, default="")
    smtp_password = models.CharField(max_length=255, blank=True, default="")
    smtp_use_tls = models.BooleanField(default=True)
    smtp_use_ssl = models.BooleanField(default=False)
    smtp_from = models.CharField(max_length=255, blank=True, default="")
    exchange_ews_url = models.CharField(max_length=512, blank=True, default="")
    exchange_domain = models.CharField(max_length=128, blank=True, default="")

    # Telegram
    telegram_bot_token = models.CharField(max_length=255, blank=True, default="")
    telegram_chat_id = models.CharField(max_length=64, blank=True, default="")
    telegram_enabled = models.BooleanField(default=False)

    # Auth providers
    auth_local_enabled = models.BooleanField(default=True)
    auth_google_enabled = models.BooleanField(default=False)
    auth_google_client_id = models.CharField(max_length=255, blank=True, default="")
    auth_google_client_secret = models.CharField(max_length=255, blank=True, default="")
    auth_sso_enabled = models.BooleanField(default=False)
    auth_sso_provider = models.CharField(
        max_length=32,
        blank=True,
        default="oidc",
        help_text="oidc | azure_ad | saml",
    )
    auth_sso_client_id = models.CharField(max_length=255, blank=True, default="")
    auth_sso_client_secret = models.CharField(max_length=255, blank=True, default="")
    auth_sso_discovery_url = models.CharField(max_length=512, blank=True, default="")
    auth_sso_tenant = models.CharField(max_length=128, blank=True, default="")
    auth_ldap_enabled = models.BooleanField(default=False)
    auth_ldap_server = models.CharField(max_length=255, blank=True, default="")
    auth_ldap_bind_dn = models.CharField(max_length=255, blank=True, default="")
    auth_ldap_base_dn = models.CharField(max_length=255, blank=True, default="")
    auth_mfa_recommended = models.BooleanField(default=True)
    auth_lockout_attempts = models.PositiveSmallIntegerField(default=5)

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
