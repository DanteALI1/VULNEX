from django.apps import AppConfig


class LicensingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "vulndb.apps.licensing"
    label = "licensing"
    verbose_name = "Лицензирование"
