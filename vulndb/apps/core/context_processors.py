from __future__ import annotations

from vulndb.apps.core.models import SystemSettings


def branding(request):
    try:
        s = SystemSettings.load()
    except Exception:
        s = None
    product = (s.product_name if s else None) or "VULNDB"
    org = (s.organization_name if s else None) or ""
    prefix = (s.local_id_prefix if s else None) or "ACME"
    return {
        "brand": {
            "product_name": product,
            "organization_name": org,
            "local_id_prefix": prefix,
            "login_title": (s.login_title if s else "") or "",
            "login_text": (s.login_text if s else "") or "",
            "logo": s.logo if s and s.logo else None,
            "setup_completed": bool(s and s.setup_completed),
            "mark": "".join(w[0] for w in product.split()[:2]).upper()[:2] or "VD",
            "auth_google_enabled": bool(s and s.auth_google_enabled and s.auth_google_client_id),
            "auth_sso_enabled": bool(s and s.auth_sso_enabled and s.auth_sso_client_id),
            "auth_lockout_attempts": (s.auth_lockout_attempts if s else 5),
        }
    }
