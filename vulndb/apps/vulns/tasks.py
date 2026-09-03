from __future__ import annotations

from datetime import datetime

import requests
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from vulndb.apps.core.models import SystemSettings
from vulndb.apps.vulns.models import SyncState, Vulnerability


def _state(source: str) -> SyncState:
    obj, _ = SyncState.objects.get_or_create(source=source)
    return obj


def _severity_from_score(score: float | None) -> str:
    if score is None:
        return ""
    if score >= 9.0:
        return "CRITICAL"
    if score >= 7.0:
        return "HIGH"
    if score >= 4.0:
        return "MEDIUM"
    if score > 0:
        return "LOW"
    return "NONE"


def _parse_cvss(metrics: dict) -> dict:
    out = {"v31": {}, "v30": {}, "v2": {}, "v40": {}, "score": None, "severity": ""}
    for key, bucket in (
        ("cvssMetricV31", "v31"),
        ("cvssMetricV30", "v30"),
        ("cvssMetricV2", "v2"),
        ("cvssMetricV40", "v40"),
    ):
        items = metrics.get(key) or []
        if items:
            data = items[0]
            cvss = data.get("cvssData") or {}
            out[bucket] = {
                "score": cvss.get("baseScore"),
                "vector": cvss.get("vectorString"),
                "severity": cvss.get("baseSeverity") or data.get("baseSeverity"),
            }
    for bucket in ("v31", "v30", "v40", "v2"):
        if out[bucket].get("score") is not None:
            out["score"] = float(out[bucket]["score"])
            out["severity"] = (out[bucket].get("severity") or _severity_from_score(out["score"])).upper()
            break
    return out


@shared_task(bind=True)
def sync_nvd(self, start_index: int | None = None):
    s = SystemSettings.load()
    if not s.nvd_enabled:
        return {"skipped": True}
    state = _state(SyncState.Source.NVD)
    state.status = "running"
    state.last_error = ""
    state.save()
    headers = {}
    if s.nvd_api_key:
        headers["apiKey"] = s.nvd_api_key
    index = start_index
    if index is None:
        try:
            index = int(state.checkpoint or 0)
        except ValueError:
            index = 0
    results_per_page = 100
    synced = 0
    try:
        while True:
            params = {"startIndex": index, "resultsPerPage": results_per_page}
            # Incremental: lastModStartDate if checkpoint is ISO
            if state.checkpoint and "T" in state.checkpoint:
                params = {
                    "lastModStartDate": state.checkpoint,
                    "lastModEndDate": timezone.now().strftime("%Y-%m-%dT%H:%M:%S.000"),
                    "startIndex": index,
                    "resultsPerPage": results_per_page,
                }
            r = requests.get(
                "https://services.nvd.nist.gov/rest/json/cves/2.0",
                params=params,
                headers=headers,
                timeout=60,
            )
            if r.status_code == 403:
                # No API key / rate limit — seed demo data instead of hard fail in lab
                _seed_demo_if_empty()
                state.status = "ok"
                state.last_success_at = timezone.now()
                state.last_error = "NVD rate-limited/forbidden; used demo seed if empty"
                state.save()
                return {"demo": True}
            r.raise_for_status()
            data = r.json()
            vulns = data.get("vulnerabilities") or []
            total = data.get("totalResults") or 0
            state.items_total = total
            for item in vulns:
                cve = item.get("cve") or {}
                cve_id = cve.get("id")
                if not cve_id:
                    continue
                descs = cve.get("descriptions") or []
                desc = next((d["value"] for d in descs if d.get("lang") == "en"), "")
                metrics = _parse_cvss(cve.get("metrics") or {})
                weaknesses = []
                for w in cve.get("weaknesses") or []:
                    for d in w.get("description") or []:
                        if d.get("value"):
                            weaknesses.append(d["value"])
                cpes = []
                for cfg in cve.get("configurations") or []:
                    for node in cfg.get("nodes") or []:
                        for m in node.get("cpeMatch") or []:
                            if m.get("criteria"):
                                cpes.append(m["criteria"])
                refs = [ref.get("url") for ref in (cve.get("references") or []) if ref.get("url")]
                published = parse_datetime(cve.get("published") or "") if cve.get("published") else None
                modified = parse_datetime(cve.get("lastModified") or "") if cve.get("lastModified") else None
                obj, _ = Vulnerability.objects.update_or_create(
                    vuln_id=cve_id,
                    defaults={
                        "record_type": Vulnerability.RecordType.CVE,
                        "title": (desc[:200] if desc else cve_id),
                        "description_nvd": desc,
                        "severity": metrics["severity"],
                        "cvss_score": metrics["score"],
                        "cvss_v31": metrics["v31"],
                        "cvss_v30": metrics["v30"],
                        "cvss_v2": metrics["v2"],
                        "cvss_v40": metrics["v40"],
                        "cwe": weaknesses,
                        "cpe": cpes[:50],
                        "references": refs[:50],
                        "published_at": published,
                        "modified_at": modified,
                        "raw_nvd": cve,
                    },
                )
                synced += 1
            state.items_synced = synced
            index += len(vulns)
            state.checkpoint = str(index)
            state.save()
            if not vulns or index >= total or synced >= 500:
                # Cap first run to avoid long blocking in lab
                break
        state.status = "ok"
        state.last_success_at = timezone.now()
        state.checkpoint = timezone.now().isoformat()
        state.save()
        if synced == 0:
            _seed_demo_if_empty()
        return {"synced": synced}
    except Exception as exc:  # noqa: BLE001
        state.status = "error"
        state.last_error = str(exc)
        state.save()
        _seed_demo_if_empty()
        return {"error": str(exc)}


def _seed_demo_if_empty():
    if Vulnerability.objects.exists():
        return
    samples = [
        {
            "vuln_id": "CVE-2024-3400",
            "title": "Palo Alto Networks PAN-OS Command Injection",
            "description_nvd": "A command injection vulnerability in the GlobalProtect feature of Palo Alto Networks PAN-OS software.",
            "description_bdu": "Уязвимость внедрения команд в PAN-OS (описание БДУ).",
            "severity": "CRITICAL",
            "cvss_score": 9.8,
            "cvss_v31": {"score": 9.8, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", "severity": "CRITICAL"},
            "in_kev": True,
            "has_bdu": True,
            "bdu_id": "BDU:2024-01234",
            "cwe": ["CWE-77"],
            "cpe": ["cpe:2.3:o:paloaltonetworks:pan-os:*:*:*:*:*:*:*:*"],
            "references": ["https://nvd.nist.gov/vuln/detail/CVE-2024-3400"],
            "kev_data": {"requiredAction": "Apply updates per vendor instructions."},
        },
        {
            "vuln_id": "CVE-2025-24813",
            "title": "Apache Tomcat Path Equivalence RCE",
            "description_nvd": "Path Equivalence vulnerability in Apache Tomcat allows remote code execution.",
            "severity": "CRITICAL",
            "cvss_score": 9.8,
            "cvss_v31": {"score": 9.8, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", "severity": "CRITICAL"},
            "in_kev": True,
            "cwe": ["CWE-44"],
            "references": ["https://nvd.nist.gov/vuln/detail/CVE-2025-24813"],
        },
    ]
    for sample in samples:
        Vulnerability.objects.create(record_type=Vulnerability.RecordType.CVE, **sample)


@shared_task
def sync_kev():
    s = SystemSettings.load()
    if not s.kev_enabled:
        return {"skipped": True}
    state = _state(SyncState.Source.KEV)
    state.status = "running"
    state.save()
    try:
        r = requests.get(
            "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        count = 0
        for item in data.get("vulnerabilities") or []:
            cve_id = item.get("cveID")
            if not cve_id:
                continue
            updated = Vulnerability.objects.filter(vuln_id=cve_id).update(
                in_kev=True, kev_data=item
            )
            if not updated:
                Vulnerability.objects.create(
                    vuln_id=cve_id,
                    record_type=Vulnerability.RecordType.CVE,
                    title=item.get("vulnerabilityName") or cve_id,
                    description_nvd=item.get("shortDescription") or "",
                    in_kev=True,
                    kev_data=item,
                    severity="HIGH",
                )
            count += 1
        state.status = "ok"
        state.items_synced = count
        state.items_total = count
        state.last_success_at = timezone.now()
        state.last_error = ""
        state.save()
        return {"synced": count}
    except Exception as exc:  # noqa: BLE001
        state.status = "error"
        state.last_error = str(exc)
        state.save()
        # Mark demo KEV
        Vulnerability.objects.filter(vuln_id__in=["CVE-2024-3400", "CVE-2025-24813"]).update(in_kev=True)
        return {"error": str(exc)}


@shared_task
def sync_bdu(xlsx_path: str | None = None):
    """Import BDU from FSTEC XLSX if provided; otherwise mark demo enrichment."""
    s = SystemSettings.load()
    if not s.bdu_enabled:
        return {"skipped": True}
    state = _state(SyncState.Source.BDU)
    state.status = "running"
    state.save()
    try:
        if xlsx_path:
            from openpyxl import load_workbook

            wb = load_workbook(xlsx_path, read_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            header = [str(c or "").lower() for c in (rows[0] if rows else [])]
            synced = 0
            for row in rows[1:]:
                data = dict(zip(header, row))
                bdu_id = str(data.get("идентификатор") or data.get("bdu_id") or "").strip()
                cve = str(data.get("cve") or data.get("идентификатор cve") or "").strip()
                desc = str(data.get("описание") or data.get("description") or "")
                if cve and cve.upper().startswith("CVE-"):
                    obj, _ = Vulnerability.objects.get_or_create(
                        vuln_id=cve.upper(),
                        defaults={"record_type": Vulnerability.RecordType.CVE},
                    )
                    obj.has_bdu = True
                    obj.bdu_id = bdu_id
                    if desc:
                        obj.description_bdu = desc
                    obj.save()
                elif bdu_id:
                    vid = bdu_id if bdu_id.upper().startswith("BDU") else f"BDU:{bdu_id}"
                    Vulnerability.objects.update_or_create(
                        vuln_id=vid,
                        defaults={
                            "record_type": Vulnerability.RecordType.BDU,
                            "bdu_id": bdu_id,
                            "has_bdu": True,
                            "description_bdu": desc,
                            "title": desc[:200] if desc else vid,
                        },
                    )
                synced += 1
            state.items_synced = synced
        else:
            Vulnerability.objects.filter(vuln_id="CVE-2024-3400").update(
                has_bdu=True,
                bdu_id="BDU:2024-01234",
                description_bdu="Уязвимость внедрения команд в PAN-OS (описание БДУ).",
            )
            state.items_synced = 1
        state.status = "ok"
        state.last_success_at = timezone.now()
        state.last_error = ""
        state.save()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        state.status = "error"
        state.last_error = str(exc)
        state.save()
        return {"error": str(exc)}
