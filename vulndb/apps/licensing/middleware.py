from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse


SKIP = ("/static/", "/media/", "/healthz", "/readyz", "/setup/", "/accounts/login")


class LicenseGateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if any(path.startswith(p) for p in SKIP):
            return self.get_response(request)
        try:
            from vulndb.apps.core.models import SystemSettings
            from vulndb.apps.licensing.services import get_license_status

            if not SystemSettings.load().setup_completed:
                return self.get_response(request)
            st = get_license_status()
            if not st.get("valid") and not st.get("grace"):
                return render(request, "licensing/blocked.html", {"license_status": st}, status=403)
        except Exception:
            pass
        return self.get_response(request)
