from __future__ import annotations

from dataclasses import dataclass

from vulndb.apps.accounts.models import Role
from vulndb.apps.tickets.models import Ticket


@dataclass
class Transition:
    action: str
    label: str
    to_status: str
    require_field: str | None = None


def available_actions(user, ticket: Ticket) -> list[Transition]:
    st = ticket.status
    actions: list[Transition] = []
    is_admin = user.has_role(Role.PLATFORM_ADMIN)
    is_analyst = user.has_role(Role.ANALYST, Role.PLATFORM_ADMIN)
    is_assignee = bool(ticket.assignee_id and ticket.assignee_id == user.id)
    is_creator = ticket.created_by_id == user.id
    can_close = is_admin or is_creator or user.can_verify()

    if st == Ticket.Status.NEW:
        if is_analyst:
            actions.append(Transition("to_triage", "В triage", Ticket.Status.TRIAGE))
            actions.append(Transition("reject", "Отклонить", Ticket.Status.REJECTED, "reject_reason"))
            actions.append(Transition("assign", "Назначить исполнителя", st, "assignee_id"))
    elif st == Ticket.Status.TRIAGE:
        if is_analyst:
            actions.append(Transition("assign", "Назначить исполнителя", st, "assignee_id"))
            actions.append(Transition("reject", "Отклонить", Ticket.Status.REJECTED, "reject_reason"))
        if (is_assignee or is_analyst) and ticket.assignee_id:
            actions.append(Transition("start", "В работу", Ticket.Status.IN_PROGRESS))
    elif st == Ticket.Status.IN_PROGRESS:
        if is_assignee or is_admin:
            actions.append(Transition("wait", "Ожидание", Ticket.Status.WAITING, "waiting_reason"))
            actions.append(Transition("resolve", "Устранено", Ticket.Status.RESOLVED, "resolution"))
    elif st == Ticket.Status.WAITING:
        if is_assignee or is_admin:
            actions.append(Transition("resume", "Вернуть в работу", Ticket.Status.IN_PROGRESS))
            actions.append(Transition("resolve", "Устранено", Ticket.Status.RESOLVED, "resolution"))
    elif st == Ticket.Status.RESOLVED:
        # Исполнитель не может сам закрыть — только постановщик / verifier / admin
        if can_close:
            actions.append(Transition("close", "Подтвердить закрытие", Ticket.Status.CLOSED))
            actions.append(
                Transition("reopen", "Вернуть в работу", Ticket.Status.IN_PROGRESS, "reopen_reason")
            )

    if is_admin and st not in {Ticket.Status.CLOSED, Ticket.Status.REJECTED}:
        actions.append(Transition("force_close", "Force close", Ticket.Status.CLOSED, "reject_reason"))

    seen: set[str] = set()
    uniq: list[Transition] = []
    for a in actions:
        if a.action not in seen:
            seen.add(a.action)
            uniq.append(a)
    return uniq


def apply_transition(user, ticket: Ticket, action: str, data: dict) -> tuple[bool, str]:
    allowed = {a.action: a for a in available_actions(user, ticket)}
    if action not in allowed:
        return False, "Действие недоступно для вашей роли или статуса заявки."

    from_status = ticket.status
    msg = ""

    if action == "assign":
        from django.contrib.auth import get_user_model

        User = get_user_model()
        assignee_id = data.get("assignee_id")
        if not assignee_id:
            return False, "Укажите исполнителя."
        assignee = User.objects.filter(pk=assignee_id).first()
        if not assignee:
            return False, "Исполнитель не найден."
        ticket.assignee = assignee
        if ticket.status == Ticket.Status.NEW:
            ticket.status = Ticket.Status.TRIAGE
        msg = f"Назначен исполнитель {assignee.display_name()}"
    elif action == "to_triage":
        ticket.status = Ticket.Status.TRIAGE
        msg = "Переведена в triage"
    elif action == "start":
        if not ticket.assignee_id:
            return False, "Сначала назначьте исполнителя."
        ticket.status = Ticket.Status.IN_PROGRESS
        msg = "Принята в работу"
    elif action == "wait":
        reason = (data.get("waiting_reason") or "").strip()
        if not reason:
            return False, "Укажите причину ожидания."
        ticket.waiting_reason = reason
        ticket.status = Ticket.Status.WAITING
        msg = f"Ожидание: {reason}"
    elif action == "resume":
        ticket.status = Ticket.Status.IN_PROGRESS
        msg = "Возврат из ожидания"
    elif action == "resolve":
        if not (user.id == ticket.assignee_id or user.has_role(Role.PLATFORM_ADMIN)):
            return False, "Устранение может отметить только исполнитель (или admin)."
        resolution = (data.get("resolution") or "").strip()
        if not resolution:
            return False, "Описание устранения обязательно."
        ticket.resolution = resolution
        ticket.status = Ticket.Status.RESOLVED
        msg = f"Устранено: {resolution}"
    elif action == "close":
        is_creator = ticket.created_by_id == user.id
        is_admin = user.has_role(Role.PLATFORM_ADMIN)
        if not (is_creator or user.can_verify() or is_admin):
            return False, "Закрыть может только постановщик или verifier."
        ticket.status = Ticket.Status.CLOSED
        msg = "Закрытие подтверждено"
    elif action == "reopen":
        reason = (data.get("reopen_reason") or "").strip()
        if not reason:
            return False, "Укажите причину возврата."
        ticket.reopen_reason = reason
        ticket.status = Ticket.Status.IN_PROGRESS
        msg = f"Возврат: {reason}"
    elif action == "reject":
        reason = (data.get("reject_reason") or "").strip()
        if not reason:
            return False, "Укажите причину отклонения."
        ticket.reject_reason = reason
        ticket.status = Ticket.Status.REJECTED
        msg = f"Отклонено: {reason}"
    elif action == "force_close":
        if not user.has_role(Role.PLATFORM_ADMIN):
            return False, "Force close только для platform_admin."
        reason = (data.get("reject_reason") or data.get("reason") or "").strip()
        if not reason:
            return False, "Укажите причину force close."
        ticket.status = Ticket.Status.CLOSED
        ticket.reject_reason = reason
        msg = f"Force close: {reason}"
    else:
        return False, "Неизвестное действие."

    ticket.save()
    from vulndb.apps.tickets.models import TicketEvent

    TicketEvent.objects.create(
        ticket=ticket,
        actor=user,
        from_status=from_status,
        to_status=ticket.status,
        message=msg,
    )
    try:
        from vulndb.apps.notify.services import notify_ticket_event

        notify_ticket_event(ticket, msg)
    except Exception:
        pass
    return True, msg
