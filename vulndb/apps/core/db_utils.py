from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote_plus

import psycopg
from django.conf import settings
from psycopg import sql


def build_database_url(
    host: str,
    port: int | str,
    name: str,
    user: str,
    password: str,
    sslmode: str = "prefer",
) -> str:
    return (
        f"postgresql://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{name}?sslmode={sslmode}"
    )


def test_connection(
    host: str,
    port: int | str,
    name: str,
    user: str,
    password: str,
    sslmode: str = "prefer",
) -> tuple[bool, str]:
    """Return (ok, russian_message)."""
    try:
        conn = psycopg.connect(
            host=host,
            port=int(port),
            dbname=name,
            user=user,
            password=password,
            sslmode=sslmode,
            connect_timeout=5,
        )
    except psycopg.OperationalError as exc:
        msg = str(exc).lower()
        if "password authentication failed" in msg or "authentication failed" in msg:
            return False, "Неверный пароль или имя пользователя PostgreSQL."
        if "does not exist" in msg and "database" in msg:
            return False, f"База данных «{name}» не существует."
        if "could not connect" in msg or "connection refused" in msg:
            return False, "PostgreSQL не запущен или недоступен по указанному адресу."
        if "timeout" in msg:
            return False, "Таймаут подключения к PostgreSQL. Проверьте host/port и firewall."
        return False, f"Ошибка подключения: {exc}"
    except Exception as exc:  # noqa: BLE001
        return False, f"Ошибка подключения: {exc}"

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.execute(
                "SELECT has_database_privilege(current_user, current_database(), 'CREATE')"
            )
            can_create = cur.fetchone()[0]
            cur.execute("SELECT has_schema_privilege(current_user, 'public', 'CREATE')")
            can_schema = cur.fetchone()[0]
        if not can_create and not can_schema:
            return False, "Подключение успешно, но нет прав CREATE на базу/схему public."
        return True, "SELECT 1 · OK · права на schema public"
    finally:
        conn.close()


def create_role_and_database(
    host: str,
    port: int | str,
    superuser: str,
    super_password: str,
    new_db: str,
    new_user: str,
    new_password: str,
    sslmode: str = "prefer",
) -> tuple[bool, str]:
    """Create role+DB as superuser. Superuser credentials must not be persisted."""
    try:
        conn = psycopg.connect(
            host=host,
            port=int(port),
            dbname="postgres",
            user=superuser,
            password=super_password,
            sslmode=sslmode,
            connect_timeout=8,
            autocommit=True,
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"Не удалось войти суперпользователем: {exc}"

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (new_user,))
            if not cur.fetchone():
                cur.execute(
                    sql.SQL("CREATE USER {} WITH PASSWORD {}").format(
                        sql.Identifier(new_user),
                        sql.Literal(new_password),
                    )
                )
            else:
                cur.execute(
                    sql.SQL("ALTER USER {} WITH PASSWORD {}").format(
                        sql.Identifier(new_user),
                        sql.Literal(new_password),
                    )
                )
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (new_db,))
            if not cur.fetchone():
                cur.execute(
                    sql.SQL("CREATE DATABASE {} OWNER {} ENCODING 'UTF8'").format(
                        sql.Identifier(new_db),
                        sql.Identifier(new_user),
                    )
                )
            cur.execute(
                sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                    sql.Identifier(new_db),
                    sql.Identifier(new_user),
                )
            )
        conn.close()

        db_conn = psycopg.connect(
            host=host,
            port=int(port),
            dbname=new_db,
            user=superuser,
            password=super_password,
            sslmode=sslmode,
            autocommit=True,
        )
        try:
            with db_conn.cursor() as cur:
                cur.execute(
                    sql.SQL("GRANT ALL ON SCHEMA public TO {}").format(sql.Identifier(new_user))
                )
                cur.execute(
                    sql.SQL(
                        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {}"
                    ).format(sql.Identifier(new_user))
                )
                cur.execute(
                    sql.SQL(
                        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {}"
                    ).format(sql.Identifier(new_user))
                )
        finally:
            db_conn.close()
    except Exception as exc:  # noqa: BLE001
        try:
            conn.close()
        except Exception:
            pass
        return False, f"Не удалось создать УЗ/БД: {exc}"

    ok, msg = test_connection(host, port, new_db, new_user, new_password, sslmode)
    if not ok:
        return False, f"УЗ создана, но проверка входа не прошла: {msg}"
    return True, "УЗ и база созданы, права выданы, вход проверен."


def upsert_env_var(key: str, value: str, env_path: str | Path | None = None) -> None:
    path = Path(env_path or settings.ENV_FILE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    pattern = re.compile(rf"^{re.escape(key)}=")
    found = False
    new_lines = []
    for line in lines:
        if pattern.match(line):
            new_lines.append(f"{key}={value}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}")
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def validate_prefix(prefix: str) -> tuple[bool, str]:
    from vulndb.apps.core.models import RESERVED_PREFIXES

    p = (prefix or "").upper().strip()
    if not re.fullmatch(r"[A-Z0-9]{2,16}", p):
        return False, "Префикс: латиница и цифры, длина 2–16."
    if p in RESERVED_PREFIXES:
        return False, f"Префикс «{p}» зарезервирован."
    return True, p
