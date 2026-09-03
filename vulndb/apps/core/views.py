from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.db.models import Q
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
from vulndb.apps.core.system_metrics import collect_system_metrics
from vulndb.apps.licensing.services import get_license_status, install_license_file

User = get_user_model()

# First-run wizard: organization → branding → DB → sources → admin → mail → finish
WIZARD_STEPS = [
    (1, "organization", "Организация"),
    (2, "branding", "Брендинг"),
    (3, "database", "База данных"),
    (4, "sources", "Источники"),
    (5, "admin", "Администратор"),
    (6, "mail", "Почта"),
    (7, "finish", "Финиш"),
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
    open_tickets = (
        Ticket.objects.exclude(status__in=["closed", "rejected"]).order_by("-updated_at")[:10]
    )
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
    max_step = len(WIZARD_STEPS)
    step = int(request.GET.get("step") or s.setup_step or 1)
    step = max(1, min(max_step, step))

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

        if step >= max_step:
            s.setup_completed = True
            s.setup_step = max_step
            s.save()
            try:
                call_command("migrate", interactive=False, verbosity=0)
            except Exception:
                pass
            try:
                from vulndb.apps.vulns.tasks import sync_bdu, sync_kev, sync_nvd

                if s.nvd_enabled:
                    sync_nvd.delay()
                if s.kev_enabled:
                    sync_kev.delay()
                if s.bdu_enabled:
                    sync_bdu.delay()
            except Exception:
                pass
            messages.success(request, "Настройка VULNDB завершена.")
            return redirect("login")

        s.setup_step = step + 1
        s.save(update_fields=["setup_step"])
        return redirect(f"{request.path}?step={s.setup_step}")

    templates = {
        1: "core/setup/organization.html",
        2: "core/setup/branding.html",
        3: "core/setup/database.html",
        4: "core/setup/sources.html",
        5: "core/setup/admin.html",
        6: "core/setup/mail.html",
        7: "core/setup/finish.html",
    }
    return render(
        request,
        templates[step],
        {
            "step": step,
            "steps": _steps_ctx(step),
            "settings_obj": s,
            "license_status": get_license_status(),
            "compose_mode": bool(getattr(settings, "DATABASE_URL", "")),
            "total_steps": max_step,
        },
    )


def _handle_step(request: HttpRequest, s: SystemSettings, step: int) -> tuple[bool, str]:
    if step == 1:
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

    if step == 2:
        s.login_title = request.POST.get("login_title", s.login_title).strip()
        s.login_text = request.POST.get("login_text", s.login_text).strip()
        s.product_name = request.POST.get("product_name", "VULNDB").strip() or "VULNDB"
        logo = request.FILES.get("logo")
        if logo:
            s.logo = logo
        s.save()
        return True, ""

    if step == 3:
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

    if step == 4:
        s.nvd_api_key = request.POST.get("nvd_api_key", "").strip()
        s.nvd_enabled = request.POST.get("nvd_enabled") == "on"
        s.kev_enabled = request.POST.get("kev_enabled") == "on"
        s.bdu_enabled = request.POST.get("bdu_enabled") == "on"
        s.bdu_xlsx_url = (
            request.POST.get("bdu_xlsx_url", "").strip()
            or "https://bdu.fstec.ru/files/documents/vullist.xlsx"
        )
        s.bdu_verify_ssl = request.POST.get("bdu_verify_ssl") == "on"
        s.nvd_sync_interval_minutes = int(request.POST.get("nvd_sync_interval_minutes") or 60)
        s.bdu_sync_interval_minutes = int(request.POST.get("bdu_sync_interval_minutes") or 1440)
        s.kev_sync_interval_minutes = int(request.POST.get("kev_sync_interval_minutes") or 360)
        s.save()
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
        if request.POST.get("skip_mail"):
            return True, ""
        s.mail_provider = request.POST.get("mail_provider", "smtp").strip() or "smtp"
        s.smtp_host = request.POST.get("smtp_host", "").strip()
        s.smtp_port = int(request.POST.get("smtp_port") or 587)
        s.smtp_user = request.POST.get("smtp_user", "").strip()
        if request.POST.get("smtp_password"):
            s.smtp_password = request.POST.get("smtp_password", "")
        s.smtp_use_tls = request.POST.get("smtp_use_tls") == "on"
        s.smtp_use_ssl = request.POST.get("smtp_use_ssl") == "on"
        s.smtp_from = request.POST.get("smtp_from", "").strip()
        s.exchange_ews_url = request.POST.get("exchange_ews_url", "").strip()
        s.exchange_domain = request.POST.get("exchange_domain", "").strip()
        s.save()
        return True, ""

    if step == 7:
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
            messages.success(request, "Брендинг сохранён.")
        elif section == "sources":
            s.nvd_api_key = request.POST.get("nvd_api_key", s.nvd_api_key)
            s.nvd_enabled = request.POST.get("nvd_enabled") == "on"
            s.kev_enabled = request.POST.get("kev_enabled") == "on"
            s.bdu_enabled = request.POST.get("bdu_enabled") == "on"
            s.bdu_xlsx_url = request.POST.get("bdu_xlsx_url", s.bdu_xlsx_url)
            s.bdu_verify_ssl = request.POST.get("bdu_verify_ssl") == "on"
            s.nvd_sync_interval_minutes = int(
                request.POST.get("nvd_sync_interval_minutes") or s.nvd_sync_interval_minutes
            )
            s.bdu_sync_interval_minutes = int(
                request.POST.get("bdu_sync_interval_minutes") or s.bdu_sync_interval_minutes
            )
            s.kev_sync_interval_minutes = int(
                request.POST.get("kev_sync_interval_minutes") or s.kev_sync_interval_minutes
            )
            s.save()
            messages.success(request, "Источники и интервалы сохранены.")
        elif section == "mail":
            s.mail_provider = request.POST.get("mail_provider", s.mail_provider)
            s.smtp_host = request.POST.get("smtp_host", "")
            s.smtp_port = int(request.POST.get("smtp_port") or 587)
            s.smtp_user = request.POST.get("smtp_user", "")
            if request.POST.get("smtp_password"):
                s.smtp_password = request.POST["smtp_password"]
            s.smtp_from = request.POST.get("smtp_from", "")
            s.smtp_use_tls = request.POST.get("smtp_use_tls") == "on"
            s.smtp_use_ssl = request.POST.get("smtp_use_ssl") == "on"
            s.exchange_ews_url = request.POST.get("exchange_ews_url", "")
            s.exchange_domain = request.POST.get("exchange_domain", "")
            s.save()
            messages.success(request, "Почта / Exchange сохранены.")
        elif section == "telegram":
            s.telegram_bot_token = request.POST.get("telegram_bot_token", "")
            s.telegram_chat_id = request.POST.get("telegram_chat_id", "")
            s.telegram_enabled = request.POST.get("telegram_enabled") == "on"
            s.save()
            messages.success(request, "Telegram сохранён.")
        elif section == "auth":
            s.auth_local_enabled = request.POST.get("auth_local_enabled") == "on"
            s.auth_google_enabled = request.POST.get("auth_google_enabled") == "on"
            s.auth_google_client_id = request.POST.get("auth_google_client_id", "")
            if request.POST.get("auth_google_client_secret"):
                s.auth_google_client_secret = request.POST.get("auth_google_client_secret", "")
            s.auth_sso_enabled = request.POST.get("auth_sso_enabled") == "on"
            s.auth_sso_provider = request.POST.get("auth_sso_provider", "oidc")
            s.auth_sso_client_id = request.POST.get("auth_sso_client_id", "")
            if request.POST.get("auth_sso_client_secret"):
                s.auth_sso_client_secret = request.POST.get("auth_sso_client_secret", "")
            s.auth_sso_discovery_url = request.POST.get("auth_sso_discovery_url", "")
            s.auth_sso_tenant = request.POST.get("auth_sso_tenant", "")
            s.auth_ldap_enabled = request.POST.get("auth_ldap_enabled") == "on"
            s.auth_ldap_server = request.POST.get("auth_ldap_server", "")
            s.auth_ldap_bind_dn = request.POST.get("auth_ldap_bind_dn", "")
            s.auth_ldap_base_dn = request.POST.get("auth_ldap_base_dn", "")
            s.auth_mfa_recommended = request.POST.get("auth_mfa_recommended") == "on"
            s.auth_lockout_attempts = int(request.POST.get("auth_lockout_attempts") or 5)
            s.save()
            messages.success(request, "Параметры аутентификации сохранены.")
        elif section == "license":
            if not getattr(settings, "LICENSE_REQUIRED", False):
                messages.info(request, "В свободной редакции лицензия не требуется.")
            else:
                lic = request.FILES.get("license_file")
                url = request.POST.get("license_server_url", "").strip()
                if url:
                    upsert_env_var("LICENSE_SERVER_URL", url)
                if lic:
                    ok, msg = install_license_file(lic.read())
                    messages.success(request, msg) if ok else messages.error(request, msg)
                else:
                    messages.info(request, "Загрузите файл .novalic для обновления лицензии.")
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
                        # Sync BDU can be heavy; run with small limit if celery unavailable
                        if source == "bdu":
                            task(limit=200)
                        else:
                            task()
                        messages.success(
                            request, f"Синхронизация {source.upper()} выполнена синхронно."
                        )
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
            "system_metrics": collect_system_metrics(),
        },
    )


@login_required
def system_metrics_api(request: HttpRequest) -> JsonResponse:
    return JsonResponse(collect_system_metrics())
