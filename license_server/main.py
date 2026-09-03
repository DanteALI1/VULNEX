"""Minimal VULNDB License Server (vendor side)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

KEYS = Path(__file__).resolve().parent / "keys"
KEYS.mkdir(exist_ok=True)
PRIV = KEYS / "private.pem"
PUB = KEYS / "public.pem"

app = FastAPI(title="VULNDB License Server", version="1.0.0")


def _ensure_keys() -> Ed25519PrivateKey:
    if PRIV.exists():
        return serialization.load_pem_private_key(PRIV.read_bytes(), password=None)
    key = Ed25519PrivateKey.generate()
    PRIV.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    PUB.write_bytes(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return key


class IssueRequest(BaseModel):
    customer: str
    fingerprint: str = "*"
    seats: int = 10


class HeartbeatRequest(BaseModel):
    license_id: str
    fingerprint: str


@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "vulndb-license-server"}


@app.post("/api/v1/issue")
def issue(req: IssueRequest):
    key = _ensure_keys()
    body = {
        "license_id": f"LIC-{datetime.now(timezone.utc).year}-{uuid.uuid4().hex[:6].upper()}",
        "customer": req.customer,
        "fingerprint": req.fingerprint,
        "seats": req.seats,
        "product": "VULNDB",
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    message = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    body["signature"] = key.sign(message).hex()
    return body


@app.post("/api/v1/heartbeat")
def heartbeat(req: HeartbeatRequest):
    if not req.license_id:
        raise HTTPException(400, "license_id required")
    return {
        "ok": True,
        "license_id": req.license_id,
        "valid": True,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/public-key")
def public_key():
    _ensure_keys()
    return {"pem": PUB.read_text(encoding="utf-8")}
