from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from vulndb.apps.accounts.models import Role
from vulndb.apps.core.db_utils import (
    build_database_url,
    create_role_and_database,
    test_connection,
    upsert_env_var,
    validate_prefix,
)
from vulndb.apps.core.models import SystemSettings
from vulndb.apps.licensing.services import get_license_status, install_license_file

User = get_user_model()

WIZARD_STEPS = [
    (1, "license", "Лицензия"),
    (2, "organization", "Организация"),
    (3, "branding", "Оформление"),
    (4, "database", "База данных"),
    (5, "admin", "Администратор"),
    (6, "sources", "Источники"),
    (7, "mail", "Почта"),
    (8, "telegram", "Telegram"),
    (9, "finish", "Финиш"),
]


def _steps_ctx(current: int) -> list[dict]:
    out = []
    for num, key, title in WIZARD_STEPS:
        out.append(
            {
                "num": num,
                "key": key,
                "title": title,
                "done": num < current,
                "active": num == current,
            }
        )
    return out


def healthz(request: HttpRequest) -> HttpResponse:
    return HttpResponse("ok", content_type="text/plain")


def readyz(request: HttpRequest) -> HttpResponse:
    try:
        SystemSettings.load()
        return HttpResponse("ready", content_type="text/plain")
    except Exception as exc:  # noqa: BLE001
        return HttpResponse(f"not ready: {exc}", status=503, content_type="text/plain")


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    from vulndb.apps.tickets.models import Ticket
    from vulndb.apps.vulns.models import SyncState, Vulnerability

    s = SystemSettings.load()
    qs = Vulnerability.objects.all()
    critical = qs.filter(severity="CRITICAL").count()
    high = qs.filter(severity="HIGH").count()
    kev = qs.filter(in_kev=True).count()
    local = qs.filter(record_type=Vulnerability.RecordType.LOCAL).count()
    attention = qs.filter(Q(severity="CRITICAL") | Q(in_kev=True)).order_by("-cvss_score")[:10]
    open_tickets = Ticket.objects.exclude(status__in=["closed", "rejected"]).order_by("-updated_at")[:10]
    syncs = SyncState.objects.all()
    return render(
        request,
        "core/dashboard.html",
        {
            "critical": critical,
            "high": high,
            "kev": kev,
            "local_count": local,
            "attention": attention,
            "open_tickets": open_tickets,
            "syncs": syncs,
            "prefix": s.local_id_prefix,
            "now": timezone.now(),
        },
    )


@require_http_methods(["GET", "POST"])
def setup_wizard(request: HttpRequest) -> HttpResponse:
    s = SystemSettings.load()
    if s.setup_completed:
        return redirect("dashboard")
    step = int(request.GET.get("step") or s.setup_step or 1)
    step = max(1, min(9, step))

    if request.method == "POST":
        action = request.POST.get("action", "next")
        if action == "back":
            s.setup_step = max(1, step - 1)
            s.save(update_fields=["setup_step"])
            return redirect(f"{request.path}?step={s.setup_step}")

        ok, err = _handle_step(request, s, step)
        if not ok:
            messages.error(request, err)
            return redirect(f"{request.path}?step={step}")

        if step >= 9:
            s.setup_completed = True
            s.setup_step = 9
            s.save()
            try:
                call_command("migrate", interactive=False, verbosity=0)
            except Exception:
                pass
            try:
                from vulndb.apps.vulns.tasks import sync_nvd

                sync_nvd.delay()
            except Exception:
                pass
            messages.success(request, "Настройка VULNDB завершена.")
            return redirect("login")

        s.setup_step = step + 1
        s.save(update_fields=["setup_step"])
        return redirect(f"{request.path}?step={s.setup_step}")

    ctx = {
        "step": step,
        "steps": _steps_ctx(step),
        "settings_obj": s,
        "license_status": get_license_status(),
        "compose_mode": bool(getattr(settings, "DATABASE_URL", "")),
    }
    template = {
        1: "core/setup/license.html",
        2: "core/setup/organization.html",
        3: "core/setup/branding.html",
        4: "core/setup/database.html",
        5: "core/setup/admin.html",
        6: "core/setup/sources.html",
        7: "core/setup/mail.html",
        8: "core/setup/telegram.html",
        9: "core/setup/finish.html",
    }[step]
    return render(request, template, ctx)


def _handle_step(request: HttpRequest, s: SystemSettings, step: int) -> tuple[bool, str]:
    if step == 1:
        lic = request.FILES.get("license_file")
        url = request.POST.get("license_server_url", "").strip()
        if url:
            upsert_env_var("LICENSE_SERVER_URL", url)
        if lic:
            ok, msg = install_license_file(lic.read())
            if not ok:
                return False, msg
        st = get_license_status()
        if not st.get("valid") and not st.get("grace"):
            # Allow continue in DEBUG / first install with demo
            if not settings.DEBUG:
                return False, "Лицензия недействительна. Загрузите .novalic или проверьте License Server."
        return True, ""

    if step == 2:
        name = request.POST.get("organization_name", "").strip()
        prefix = request.POST.get("local_id_prefix", "").strip()
        ok, result = validate_prefix(prefix)
        if not ok:
            return False, result
        if not name:
            return False, "Укажите название организации."
        s.organization_name = name
        s.local_id_prefix = result
        s.save()
        return True, ""

    if step == 3:
        s.login_title = request.POST.get("login_title", s.login_title).strip()
        s.login_text = request.POST.get("login_text", s.login_text).strip()
        s.product_name = request.POST.get("product_name", "VULNDB").strip() or "VULNDB"
        logo = request.FILES.get("logo")
        if logo:
            s.logo = logo
        s.save()
        return True, ""

    if step == 4:
        mode = request.POST.get("db_mode", "connect")
        if mode == "skip_compose" or request.POST.get("compose_ok"):
            s.db_configured = True
            s.save(update_fields=["db_configured"])
            return True, ""
        host = request.POST.get("db_host", "127.0.0.1").strip()
        port = request.POST.get("db_port", "5432").strip()
        name = request.POST.get("db_name", "vulndb").strip()
        user = request.POST.get("db_user", "vulndb").strip()
        password = request.POST.get("db_password", "")
        sslmode = request.POST.get("db_sslmode", "prefer").strip() or "prefer"

        if mode == "create":
            su = request.POST.get("pg_superuser", "postgres").strip()
            su_pass = request.POST.get("pg_super_password", "")
            new_pass2 = request.POST.get("db_password2", "")
            if password != new_pass2:
                return False, "Пароли новой УЗ не совпадают."
            ok, msg = create_role_and_database(
                host, port, su, su_pass, name, user, password, sslmode
            )
            if not ok:
                return False, msg
        else:
            ok, msg = test_connection(host, port, name, user, password, sslmode)
            if not ok:
                return False, msg

        url = build_database_url(host, port, name, user, password, sslmode)
        upsert_env_var("DATABASE_URL", url)
        s.db_host = host
        s.db_port = int(port)
        s.db_name = name
        s.db_user = user
        s.db_sslmode = sslmode
        s.db_configured = True
        s.save()
        try:
            call_command("migrate", interactive=False, verbosity=0)
        except Exception as exc:  # noqa: BLE001
            return False, f"Подключение OK, но migrate не удался: {exc}"
        return True, ""

    if step == 5:
        username = request.POST.get("username", "").strip()
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")
        if not username or not password:
            return False, "Укажите логин и пароль администратора VULNDB."
        if password != password2:
            return False, "Пароли не совпадают."
        if User.objects.filter(username=username).exists():
            u = User.objects.get(username=username)
            u.set_password(password)
            u.full_name = full_name
            u.email = email
            u.role = Role.PLATFORM_ADMIN
            u.is_staff = True
            u.is_superuser = True
            u.save()
        else:
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                full_name=full_name,
                role=Role.PLATFORM_ADMIN,
            )
        return True, ""

    if step == 6:
        s.nvd_api_key = request.POST.get("nvd_api_key", "").strip()
        s.nvd_enabled = request.POST.get("nvd_enabled") == "on"
        s.kev_enabled = request.POST.get("kev_enabled") == "on"
        s.bdu_enabled = request.POST.get("bdu_enabled") == "on"
        s.sync_cron_hint = request.POST.get("sync_cron_hint", "hourly").strip()
        s.save()
        return True, ""

    if step == 7:
        s.smtp_host = request.POST.get("smtp_host", "").strip()
        s.smtp_port = int(request.POST.get("smtp_port") or 587)
        s.smtp_user = request.POST.get("smtp_user", "").strip()
        if request.POST.get("smtp_password"):
            s.smtp_password = request.POST.get("smtp_password", "")
        s.smtp_use_tls = request.POST.get("smtp_use_tls") == "on"
        s.smtp_from = request.POST.get("smtp_from", "").strip()
        s.save()
        return True, ""

    if step == 8:
        if request.POST.get("skip_telegram"):
            return True, ""
        s.telegram_bot_token = request.POST.get("telegram_bot_token", "").strip()
        s.telegram_chat_id = request.POST.get("telegram_chat_id", "").strip()
        s.telegram_enabled = bool(s.telegram_bot_token)
        s.save()
        return True, ""

    if step == 9:
        return True, ""

    return False, "Неизвестный шаг."


@require_POST
def setup_db_test(request: HttpRequest) -> JsonResponse:
    host = request.POST.get("db_host", "127.0.0.1")
    port = request.POST.get("db_port", "5432")
    name = request.POST.get("db_name", "vulndb")
    user = request.POST.get("db_user", "vulndb")
    password = request.POST.get("db_password", "")
    sslmode = request.POST.get("db_sslmode", "prefer")
    ok, msg = test_connection(host, port, name, user, password, sslmode)
    return JsonResponse({"ok": ok, "message": msg})


@require_POST
def setup_db_create(request: HttpRequest) -> JsonResponse:
    ok, msg = create_role_and_database(
        request.POST.get("db_host", "127.0.0.1"),
        request.POST.get("db_port", "5432"),
        request.POST.get("pg_superuser", "postgres"),
        request.POST.get("pg_super_password", ""),
        request.POST.get("db_name", "vulndb"),
        request.POST.get("db_user", "vulndb"),
        request.POST.get("db_password", ""),
        request.POST.get("db_sslmode", "prefer"),
    )
    return JsonResponse({"ok": ok, "message": msg})


@login_required
@require_http_methods(["GET", "POST"])
def app_settings(request: HttpRequest) -> HttpResponse:
    s = SystemSettings.load()
    tab = request.GET.get("tab") or request.POST.get("tab") or "org"
    if request.method == "POST":
        if not request.user.has_role(Role.PLATFORM_ADMIN):
            messages.error(request, "Недостаточно прав.")
            return redirect("app_settings")
        section = request.POST.get("section", tab)
        if section == "org":
            ok, result = validate_prefix(request.POST.get("local_id_prefix", ""))
            if not ok:
                messages.error(request, result)
            else:
                s.organization_name = request.POST.get("organization_name", s.organization_name)
                s.local_id_prefix = result
                s.save()
                messages.success(request, "Организация сохранена.")
        elif section == "branding":
            s.login_title = request.POST.get("login_title", s.login_title)
            s.login_text = request.POST.get("login_text", s.login_text)
            s.product_name = request.POST.get("product_name", s.product_name) or "VULNDB"
            if request.FILES.get("logo"):
                s.logo = request.FILES["logo"]
            s.save()
            messages.success(request, "Оформление сохранено.")
        elif section == "sources":
            s.nvd_api_key = request.POST.get("nvd_api_key", s.nvd_api_key)
            s.nvd_enabled = request.POST.get("nvd_enabled") == "on"
            s.kev_enabled = request.POST.get("kev_enabled") == "on"
            s.bdu_enabled = request.POST.get("bdu_enabled") == "on"
            s.save()
            messages.success(request, "Источники сохранены.")
        elif section == "mail":
            s.smtp_host = request.POST.get("smtp_host", "")
            s.smtp_port = int(request.POST.get("smtp_port") or 587)
            s.smtp_user = request.POST.get("smtp_user", "")
            if request.POST.get("smtp_password"):
                s.smtp_password = request.POST["smtp_password"]
            s.smtp_from = request.POST.get("smtp_from", "")
            s.smtp_use_tls = request.POST.get("smtp_use_tls") == "on"
            s.save()
            messages.success(request, "Почта сохранена.")
        elif section == "telegram":
            s.telegram_bot_token = request.POST.get("telegram_bot_token", "")
            s.telegram_chat_id = request.POST.get("telegram_chat_id", "")
            s.telegram_enabled = request.POST.get("telegram_enabled") == "on"
            s.save()
            messages.success(request, "Telegram сохранён.")
        elif section == "sync":
            source = request.POST.get("run_sync")
            if source:
                from vulndb.apps.vulns import tasks as sync_tasks

                mapping = {
                    "nvd": sync_tasks.sync_nvd,
                    "kev": sync_tasks.sync_kev,
                    "bdu": sync_tasks.sync_bdu,
                }
                task = mapping.get(source)
                if task:
                    try:
                        task.delay()
                        messages.success(request, f"Запущена синхронизация {source.upper()}.")
                    except Exception:
                        task()
                        messages.success(request, f"Синхронизация {source.upper()} выполнена синхронно.")
        return redirect(f"/settings/#{section}")

    from vulndb.apps.vulns.models import SyncState

    return render(
        request,
        "core/settings.html",
        {
            "settings_obj": s,
            "syncs": SyncState.objects.all(),
            "license_status": get_license_status(),
            "active_tab": tab,
        },
    )
