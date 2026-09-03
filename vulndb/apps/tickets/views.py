from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from vulndb.apps.accounts.models import Role
from vulndb.apps.audit.services import log_action
from vulndb.apps.tickets.models import Ticket, TicketEvent
from vulndb.apps.tickets.workflow import apply_transition, available_actions
from vulndb.apps.vulns.models import Vulnerability

User = get_user_model()


@login_required
def ticket_list(request: HttpRequest) -> HttpResponse:
    qs = Ticket.objects.select_related("vulnerability", "assignee", "created_by")
    view = request.GET.get("view", "open")
    if view == "open":
        qs = qs.exclude(status__in=[Ticket.Status.CLOSED, Ticket.Status.REJECTED])
    elif view == "mine":
        qs = qs.filter(assignee=request.user)
    elif view == "confirm":
        qs = qs.filter(status=Ticket.Status.RESOLVED)
    elif view == "closed":
        qs = qs.filter(status__in=[Ticket.Status.CLOSED, Ticket.Status.REJECTED])
    tickets = list(qs[:200])
    selected_id = request.GET.get("id")
    selected = None
    if selected_id:
        selected = get_object_or_404(Ticket, number=selected_id)
    elif tickets:
        selected = tickets[0]
    actions = available_actions(request.user, selected) if selected else []
    assignees = User.objects.filter(
        role__in=[Role.TICKET_ASSIGNEE, Role.ANALYST, Role.PLATFORM_ADMIN]
    ).order_by("username")
    return render(
        request,
        "tickets/list.html",
        {
            "tickets": tickets,
            "selected": selected,
            "actions": actions,
            "assignees": assignees,
            "view": view,
            "vulns": Vulnerability.objects.order_by("-updated_at")[:100],
        },
    )


@login_required
@require_POST
def ticket_create(request: HttpRequest) -> HttpResponse:
    if not request.user.has_role(Role.ANALYST, Role.PLATFORM_ADMIN):
        messages.error(request, "Недостаточно прав.")
        return redirect("ticket_list")
    vuln_id = request.POST.get("vuln_id")
    title = request.POST.get("title", "").strip()
    priority = request.POST.get("priority", Ticket.Priority.P2)
    description = request.POST.get("description", "").strip()
    vuln = get_object_or_404(Vulnerability, vuln_id=vuln_id)
    if not title:
        title = f"Устранение {vuln.vuln_id}"
    with transaction.atomic():
        ticket = Ticket.objects.create(
            number=Ticket.next_number(),
            title=title,
            description=description,
            priority=priority,
            vulnerability=vuln,
            created_by=request.user,
            status=Ticket.Status.NEW,
        )
        TicketEvent.objects.create(
            ticket=ticket,
            actor=request.user,
            from_status="",
            to_status=Ticket.Status.NEW,
            message="Заявка создана",
        )
    log_action(request.user, "ticket.create", ticket.display_id, request=request)
    messages.success(request, f"Создана {ticket.display_id}")
    return redirect(f"/tickets/?id={ticket.number}")


@login_required
@require_POST
def ticket_action(request: HttpRequest, number: int) -> HttpResponse:
    ticket = get_object_or_404(Ticket, number=number)
    action = request.POST.get("action", "")
    ok, msg = apply_transition(request.user, ticket, action, request.POST)
    if ok:
        log_action(request.user, f"ticket.{action}", f"{ticket.display_id}: {msg}", request=request)
        messages.success(request, msg)
    else:
        messages.error(request, msg)
    return redirect(f"/tickets/?id={ticket.number}")
