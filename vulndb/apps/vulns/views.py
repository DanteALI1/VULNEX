from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from vulndb.apps.accounts.models import Role
from vulndb.apps.audit.services import log_action
from vulndb.apps.core.models import SystemSettings
from vulndb.apps.vulns.models import LocalIdSequence, Vulnerability


@login_required
def vuln_list(request: HttpRequest) -> HttpResponse:
    qs = Vulnerability.objects.all()
    q = request.GET.get("q", "").strip()
    record_type = request.GET.get("type", "")
    cvss_min = request.GET.get("cvss_min")
    cvss_max = request.GET.get("cvss_max")
    severities = request.GET.getlist("severity")
    kev = request.GET.get("kev")
    local_only = request.GET.get("local")
    days = request.GET.get("days")

    chips = []
    if q:
        qs = qs.filter(
            Q(vuln_id__icontains=q)
            | Q(title__icontains=q)
            | Q(description_nvd__icontains=q)
            | Q(description_bdu__icontains=q)
            | Q(bdu_id__icontains=q)
        )
        chips.append(("q", f"Поиск: {q}"))
    if record_type == "cve":
        qs = qs.filter(record_type=Vulnerability.RecordType.CVE)
        chips.append(("type", "Только CVE"))
    elif record_type == "bdu":
        qs = qs.filter(Q(has_bdu=True) | Q(record_type=Vulnerability.RecordType.BDU))
        chips.append(("type", "С BDU"))
    elif record_type == "local":
        qs = qs.filter(record_type=Vulnerability.RecordType.LOCAL)
        chips.append(("type", "Локальные"))
    if severities:
        qs = qs.filter(severity__in=[s.upper() for s in severities])
        chips.append(("severity", "Severity: " + ", ".join(severities)))
    if cvss_min:
        qs = qs.filter(cvss_score__gte=float(cvss_min))
        chips.append(("cvss_min", f"CVSS ≥ {cvss_min}"))
    if cvss_max:
        qs = qs.filter(cvss_score__lte=float(cvss_max))
        chips.append(("cvss_max", f"CVSS ≤ {cvss_max}"))
    if kev:
        qs = qs.filter(in_kev=True)
        chips.append(("kev", "KEV"))
    if local_only:
        qs = qs.filter(record_type=Vulnerability.RecordType.LOCAL)
    if days:
        from datetime import timedelta

        from django.utils import timezone

        qs = qs.filter(modified_at__gte=timezone.now() - timedelta(days=int(days)))
        chips.append(("days", f"{days} дней"))

    s = SystemSettings.load()
    total = qs.count()
    page = list(qs[:100])
    return render(
        request,
        "vulns/list.html",
        {
            "vulns": page,
            "total": total,
            "chips": chips,
            "filters": request.GET,
            "prefix": s.local_id_prefix,
        },
    )


@login_required
def vuln_detail(request: HttpRequest, vuln_id: str) -> HttpResponse:
    vuln = get_object_or_404(Vulnerability, vuln_id=vuln_id)
    tickets = vuln.tickets.all().order_by("-created_at")[:20]
    return render(request, "vulns/detail.html", {"vuln": vuln, "tickets": tickets})


@login_required
@require_http_methods(["GET", "POST"])
def vuln_create_local(request: HttpRequest) -> HttpResponse:
    if not request.user.has_role(Role.ANALYST, Role.PLATFORM_ADMIN):
        return redirect("vuln_list")
    s = SystemSettings.load()
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        severity = request.POST.get("severity", "HIGH").upper()
        score = request.POST.get("cvss_score") or None
        with transaction.atomic():
            vid = LocalIdSequence.next_id(s.local_id_prefix)
            vuln = Vulnerability.objects.create(
                vuln_id=vid,
                record_type=Vulnerability.RecordType.LOCAL,
                title=title or vid,
                description_nvd=description,
                severity=severity,
                cvss_score=float(score) if score else None,
            )
        log_action(request.user, "vuln.create_local", f"Создана {vid}", request=request)
        return redirect("vuln_detail", vuln_id=vuln.vuln_id)
    return render(request, "vulns/create_local.html", {"prefix": s.local_id_prefix})
