from celery import shared_task
from django.conf import settings
from django.utils import timezone

from vulndb.apps.licensing.models import LicenseState
from vulndb.apps.licensing.services import get_license_status, machine_fingerprint


@shared_task
def license_heartbeat():
    # Free edition: не делаем онлайн-проверку/heartbeat.
    if not getattr(settings, "LICENSE_REQUIRED", False):
        return {"skipped": True}

    import requests

    st = get_license_status()
    state, _ = LicenseState.objects.get_or_create(pk=1)
    try:
        r = requests.post(
            f"{settings.LICENSE_SERVER_URL.rstrip('/')}/api/v1/heartbeat",
            json={
                "license_id": st.get("license_id"),
                "fingerprint": machine_fingerprint(),
            },
            timeout=10,
        )
        if r.ok:
            state.valid = True
            state.in_grace = False
            state.last_heartbeat_at = timezone.now()
            state.last_verified_at = timezone.now()
            state.last_error = ""
            state.save()
            return {"ok": True}
        state.last_error = r.text[:500]
        state.save(update_fields=["last_error"])
        return {"ok": False, "error": r.text}
    except Exception as exc:  # noqa: BLE001
        state.last_error = str(exc)
        state.save(update_fields=["last_error"])
        return {"ok": False, "error": str(exc)}
