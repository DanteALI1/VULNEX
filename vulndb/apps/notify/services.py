from __future__ import annotations

from django.conf import settings
from django.core.mail import send_mail

from vulndb.apps.core.models import SystemSettings
from vulndb.apps.notify.models import NotificationLog


def notify_ticket_event(ticket, message: str) -> None:
    s = SystemSettings.load()
    subject = f"VULNDB {ticket.display_id}: {message}"
    body = f"{ticket.display_id}\n{ticket.title}\n{ticket.vulnerability.vuln_id}\n\n{message}"
    recipients = set()
    if ticket.created_by and ticket.created_by.email:
        recipients.add(ticket.created_by.email)
    if ticket.assignee and ticket.assignee.email:
        recipients.add(ticket.assignee.email)
    if s.smtp_host and recipients:
        try:
            send_mail(
                subject,
                body,
                s.smtp_from or settings.DEFAULT_FROM_EMAIL,
                list(recipients),
                fail_silently=False,
            )
            NotificationLog.objects.create(
                channel="email",
                recipient=",".join(recipients),
                subject=subject,
                body=body,
                ok=True,
            )
        except Exception as exc:  # noqa: BLE001
            NotificationLog.objects.create(
                channel="email",
                recipient=",".join(recipients),
                subject=subject,
                body=body,
                ok=False,
                error=str(exc),
            )
    if s.telegram_enabled and s.telegram_bot_token and s.telegram_chat_id:
        try:
            import requests

            r = requests.post(
                f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage",
                json={"chat_id": s.telegram_chat_id, "text": f"{subject}\n{body}"},
                timeout=15,
            )
            NotificationLog.objects.create(
                channel="telegram",
                recipient=s.telegram_chat_id,
                subject=subject,
                body=body,
                ok=r.ok,
                error="" if r.ok else r.text[:500],
            )
        except Exception as exc:  # noqa: BLE001
            NotificationLog.objects.create(
                channel="telegram",
                recipient=s.telegram_chat_id,
                subject=subject,
                body=body,
                ok=False,
                error=str(exc),
            )
