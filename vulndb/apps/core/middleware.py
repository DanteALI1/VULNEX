from __future__ import annotations

from django.shortcuts import redirect
from django.urls import reverse
from django.utils.functional import SimpleLazyObject


SKIP_PREFIXES = (
    "/static/",
    "/media/",
    "/healthz",
    "/readyz",
    "/setup/",
    "/admin/login",
)


class SetupWizardMiddleware:
    """Redirect all traffic to setup wizard until setup_completed."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if any(path.startswith(p) for p in SKIP_PREFIXES):
            return self.get_response(request)
        try:
            from vulndb.apps.core.models import SystemSettings

            settings_obj = SystemSettings.load()
        except Exception:
            # DB not ready — allow setup paths only
            if not path.startswith("/setup/"):
                return redirect("setup_wizard")
            return self.get_response(request)

        if not settings_obj.setup_completed and not path.startswith("/setup/"):
            return redirect("setup_wizard")
        return self.get_response(request)
