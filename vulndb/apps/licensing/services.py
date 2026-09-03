from __future__ import annotations

import hashlib
import json
import platform
import socket
import uuid
from datetime import timedelta
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from django.conf import settings
from django.utils import timezone

from vulndb.apps.licensing.models import LicenseState


def machine_fingerprint() -> str:
    raw = "|".join(
        [
            platform.node(),
            platform.system(),
            platform.machine(),
            hex(uuid.getnode()),
            socket.gethostname(),
        ]
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _public_key() -> Ed25519PublicKey | None:
    pem = Path(settings.BASE_DIR) / "license_server" / "keys" / "public.pem"
    if not pem.exists():
        return None
    return serialization.load_pem_public_key(pem.read_bytes())


def install_license_file(data: bytes) -> tuple[bool, str]:
    try:
        payload = json.loads(data.decode("utf-8"))
    except Exception:
        return False, "Файл .novalic повреждён или не JSON."
    path = Path(settings.LICENSE_FILE)
    path.write_bytes(data)
    state, _ = LicenseState.objects.get_or_create(pk=1)
    state.raw_license = payload
    state.license_id = payload.get("license_id", "")
    state.customer = payload.get("customer", "")
    state.fingerprint_expected = payload.get("fingerprint", "")
    state.last_verified_at = timezone.now()
    state.valid = _verify_payload(payload)
    state.in_grace = False
    state.save()
    if not state.valid:
        return False, "Подпись лицензии недействительна или fingerprint не совпадает."
    return True, "Лицензия установлена."


def _verify_payload(payload: dict) -> bool:
    pub = _public_key()
    if pub is None:
        # Dev mode without keys: accept structurally valid licenses
        return bool(payload.get("license_id"))
    sig_hex = payload.get("signature", "")
    body = {k: v for k, v in payload.items() if k != "signature"}
    message = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    try:
        pub.verify(bytes.fromhex(sig_hex), message)
    except (InvalidSignature, ValueError):
        return False
    fp = payload.get("fingerprint")
    if fp and fp != machine_fingerprint() and fp != "*":
        return False
    return True


def get_license_status() -> dict:
    try:
        state = LicenseState.objects.filter(pk=1).first()
    except Exception:
        state = None
    path = Path(settings.LICENSE_FILE)
    if state is None and path.exists():
        try:
            install_license_file(path.read_bytes())
            state = LicenseState.objects.filter(pk=1).first()
        except Exception:
            state = None

    if state is None:
        # DEBUG: allow grace-like demo so wizard can proceed
        if settings.DEBUG:
            return {
                "valid": True,
                "grace": False,
                "status": "demo",
                "license_id": "DEMO-DEV",
                "customer": "Development",
                "fingerprint": machine_fingerprint(),
                "message": "Режим разработки (DEBUG)",
            }
        return {
            "valid": False,
            "grace": False,
            "status": "missing",
            "fingerprint": machine_fingerprint(),
            "message": "Лицензия не установлена",
        }

    valid = bool(state.valid)
    grace = False
    if not valid and state.last_verified_at:
        grace_until = state.last_verified_at + timedelta(days=settings.LICENSE_GRACE_DAYS)
        grace = timezone.now() < grace_until
    return {
        "valid": valid,
        "grace": grace,
        "status": "online" if valid else ("grace" if grace else "invalid"),
        "license_id": state.license_id,
        "customer": state.customer,
        "fingerprint": machine_fingerprint(),
        "last_verified_at": state.last_verified_at,
        "message": "Online" if valid else ("Grace period" if grace else "Invalid"),
    }


def sign_license(payload: dict, private_key: Ed25519PrivateKey) -> dict:
    body = dict(payload)
    body.pop("signature", None)
    message = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    sig = private_key.sign(message).hex()
    body["signature"] = sig
    return body
