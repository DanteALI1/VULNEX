from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from vulndb.apps.accounts.forms import LocalUserCreateForm, LocalUserEditForm
from vulndb.apps.accounts.models import Role, User
from vulndb.apps.audit.services import log_action


class VulndbLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


def platform_admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(request: HttpRequest, *args, **kwargs):
        if not request.user.has_role(Role.PLATFORM_ADMIN):
            messages.error(request, "Создавать и менять пользователей может только администратор.")
            return redirect("dashboard")
        return view(request, *args, **kwargs)

    return wrapped


def _admin_count() -> int:
    return User.objects.filter(role=Role.PLATFORM_ADMIN, is_active=True).count()


@platform_admin_required
@require_http_methods(["GET", "POST"])
def user_list(request: HttpRequest) -> HttpResponse:
    form = LocalUserCreateForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            user = form.save()
            log_action(
                request.user,
                "user.create",
                f"{user.username} · {user.get_role_display()}",
                request,
            )
            messages.success(request, f"Создан пользователь {user.username} ({user.get_role_display()}).")
            return redirect("user_list")
        messages.error(request, "Проверьте форму: пользователь не создан.")
    users = User.objects.order_by("username")
    return render(
        request,
        "accounts/users.html",
        {"form": form, "users": users, "role_choices": Role.choices},
    )


@platform_admin_required
@require_http_methods(["GET", "POST"])
def user_edit(request: HttpRequest, user_id: int) -> HttpResponse:
    target = get_object_or_404(User, pk=user_id)
    original_role = target.role
    original_active = target.is_active
    form = LocalUserEditForm(request.POST or None, instance=target)
    if request.method == "POST":
        if form.is_valid():
            new_role = form.cleaned_data["role"]
            new_active = form.cleaned_data["is_active"]
            was_admin = original_role == Role.PLATFORM_ADMIN and original_active
            losing_admin = was_admin and (new_role != Role.PLATFORM_ADMIN or not new_active)
            if losing_admin and _admin_count() <= 1:
                messages.error(request, "Нельзя снять последнего активного администратора.")
                return redirect("user_edit", user_id=target.pk)
            if target.pk == request.user.pk and not new_active:
                messages.error(request, "Нельзя отключить собственную учётку.")
                return redirect("user_edit", user_id=target.pk)
            form.save()
            log_action(
                request.user,
                "user.update",
                f"{target.username} · {target.get_role_display()}",
                request,
            )
            messages.success(request, f"Пользователь {target.username} сохранён.")
            return redirect("user_list")
        messages.error(request, "Проверьте форму: изменения не сохранены.")
    return render(
        request,
        "accounts/user_edit.html",
        {"form": form, "target": target},
    )
