from __future__ import annotations

from vulndb.apps.audit.models import AuditEntry


def log_action(user, action: str, message: str = "", request=None) -> None:
    ip = None
    path = ""
    if request is not None:
        ip = request.META.get("REMOTE_ADDR")
        path = request.path
    try:
        AuditEntry.objects.create(
            actor=user if getattr(user, "is_authenticated", False) else None,
            action=action,
            message=message,
            ip=ip,
            path=path,
        )
    except Exception:
        pass
