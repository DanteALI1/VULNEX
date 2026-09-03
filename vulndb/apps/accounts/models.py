from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    PLATFORM_ADMIN = "platform_admin", "Platform Admin"
    ANALYST = "analyst", "Аналитик"
    TICKET_ASSIGNEE = "ticket_assignee", "Исполнитель"
    VERIFIER = "verifier", "Verifier"


class User(AbstractUser):
    full_name = models.CharField("ФИО", max_length=255, blank=True)
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.ANALYST)
    is_verifier = models.BooleanField(
        default=False,
        help_text="Флаг verifier на профиле аналитика",
    )
    telegram_chat_id = models.CharField(max_length=64, blank=True)

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def display_name(self) -> str:
        return self.full_name or self.get_full_name() or self.username

    def initials(self) -> str:
        name = self.display_name()
        parts = [p for p in name.replace(".", " ").split() if p]
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return (name[:2] or "??").upper()

    @property
    def role_label(self) -> str:
        return self.get_role_display()

    def has_role(self, *roles: str) -> bool:
        if self.is_superuser or self.role == Role.PLATFORM_ADMIN:
            return True
        return self.role in roles

    def can_verify(self) -> bool:
        return self.has_role(Role.PLATFORM_ADMIN) or self.is_verifier or self.role == Role.VERIFIER
