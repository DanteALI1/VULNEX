from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class Ticket(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "new"
        TRIAGE = "triage", "triage"
        IN_PROGRESS = "in_progress", "in_progress"
        WAITING = "waiting", "waiting"
        RESOLVED = "resolved", "resolved"
        CLOSED = "closed", "closed"
        REJECTED = "rejected", "rejected"

    class Priority(models.TextChoices):
        P1 = "p1", "P1"
        P2 = "p2", "P2"
        P3 = "p3", "P3"
        P4 = "p4", "P4"

    number = models.PositiveIntegerField(unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.NEW, db_index=True)
    priority = models.CharField(max_length=8, choices=Priority.choices, default=Priority.P2)

    vulnerability = models.ForeignKey(
        "vulns.Vulnerability",
        on_delete=models.CASCADE,
        related_name="tickets",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tickets_created",
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets_assigned",
    )
    waiting_reason = models.TextField(blank=True, default="")
    resolution = models.TextField(blank=True, default="")
    reject_reason = models.TextField(blank=True, default="")
    reopen_reason = models.TextField(blank=True, default="")
    sla_due_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Заявка"
        verbose_name_plural = "Заявки"

    def __str__(self) -> str:
        return f"T-{self.number}"

    @property
    def display_id(self) -> str:
        return f"T-{self.number}"

    @classmethod
    def next_number(cls) -> int:
        last = cls.objects.order_by("-number").values_list("number", flat=True).first()
        return (last or 1000) + 1


class TicketEvent(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    from_status = models.CharField(max_length=32, blank=True, default="")
    to_status = models.CharField(max_length=32, blank=True, default="")
    message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
