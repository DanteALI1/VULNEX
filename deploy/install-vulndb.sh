#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# install-vulndb.sh — установка VULNDB на РЕД ОС 8 / RHEL-like
# Запуск: sudo bash install-vulndb.sh
# ──────────────────────────────────────────────────────────
set -euo pipefail

VULNDB_HOME="/opt/vulndb"
VULNDB_MEDIA="/var/lib/vulndb/media"
VULNDB_LOGS="/var/log/vulndb"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✔${NC} $*"; }
fail() { echo -e "${RED}✖${NC} $*"; }
step() { echo -e "\n==> $*"; }

die() { fail "$@"; exit 1; }

need_root() {
    [[ $EUID -eq 0 ]] || die "Скрипт должен запускаться от root (sudo)"
}

# ── 1. Системные пакеты ──────────────────────────────────
install_packages() {
    step "Установка системных пакетов (dnf)"
    dnf -y install \
        git curl wget tar gzip \
        postgresql-server postgresql \
        redis nginx firewalld \
        gcc gcc-c++ make libpq-devel \
        python3 python3-devel python3-pip

    local py
    py="$(python3 --version 2>&1)" || die "python3 не найден"
    ok "Python: $py"
}

# ── 2. PostgreSQL ─────────────────────────────────────────
setup_postgres() {
    step "Инициализация PostgreSQL"

    # Determine PGDATA — support both standard and Red OS layouts
    local pgdata=""
    for candidate in /var/lib/pgsql/data /var/lib/postgresql/data; do
        [[ -d "$candidate" ]] && pgdata="$candidate" && break
    done

    # initdb only if PGDATA is missing or empty (no PG_VERSION file)
    if [[ -z "$pgdata" ]] || [[ ! -f "$pgdata/PG_VERSION" ]]; then
        if command -v postgresql-setup &>/dev/null; then
            postgresql-setup --initdb 2>/dev/null || true
        elif [[ -x /usr/bin/postgresql-setup ]]; then
            /usr/bin/postgresql-setup --initdb 2>/dev/null || true
        else
            die "postgresql-setup не найден"
        fi
        # Re-detect pgdata after initdb
        for candidate in /var/lib/pgsql/data /var/lib/postgresql/data; do
            [[ -d "$candidate" ]] && pgdata="$candidate" && break
        done
    fi

    [[ -n "$pgdata" && -f "$pgdata/PG_VERSION" ]] || die "PGDATA не инициализирована"

    # Fix pg_hba.conf authentication before starting the service
    local hba="$pgdata/pg_hba.conf"
    if [[ -f "$hba" ]]; then
        sed -i 's/\bident\b/scram-sha-256/g; s/\bpeer\b/scram-sha-256/g' "$hba"
    fi

    # Start PostgreSQL — handle "already running" gracefully
    systemctl enable postgresql
    if systemctl is-active --quiet postgresql; then
        systemctl reload postgresql || systemctl restart postgresql
        ok "PostgreSQL уже запущен, конфигурация перезагружена"
    else
        systemctl start postgresql || die "Не удалось запустить PostgreSQL"
        ok "PostgreSQL запущен"
    fi
}

# ── 3. Создание БД ───────────────────────────────────────
create_db() {
    step "Создание БД и пользователя vulndb"

    local db_pass="${VULNDB_DB_PASSWORD:-CHANGE_ME_DB_PASSWORD}"

    sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='vulndb'" \
        | grep -q 1 && ok "Роль vulndb уже существует" || \
        sudo -u postgres psql -c "CREATE USER vulndb WITH PASSWORD '${db_pass}';"

    sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='vulndb'" \
        | grep -q 1 && ok "БД vulndb уже существует" || \
        sudo -u postgres psql -c "CREATE DATABASE vulndb OWNER vulndb ENCODING 'UTF8';"

    sudo -u postgres psql -d vulndb -c "
        GRANT ALL PRIVILEGES ON DATABASE vulndb TO vulndb;
        GRANT ALL ON SCHEMA public TO vulndb;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO vulndb;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO vulndb;
    " >/dev/null

    ok "БД vulndb готова"
}

# ── 4. Redis ──────────────────────────────────────────────
setup_redis() {
    step "Запуск Redis"
    systemctl enable --now redis || systemctl enable --now redis-server || die "Не удалось запустить Redis"
    redis-cli PING | grep -q PONG || die "Redis не отвечает PONG"
    ok "Redis работает"
}

# ── 5. Приложение ─────────────────────────────────────────
setup_app() {
    step "Настройка приложения"

    id vulndb &>/dev/null || useradd --system --home "$VULNDB_HOME" --shell /sbin/nologin vulndb
    mkdir -p "$VULNDB_HOME" "$VULNDB_MEDIA" "$VULNDB_LOGS"

    # Copy or link source code into VULNDB_HOME if not already there
    if [[ "$REPO_DIR" != "$VULNDB_HOME" ]]; then
        cp -a "$REPO_DIR/." "$VULNDB_HOME/"
    fi

    chown -R vulndb:vulndb "$VULNDB_HOME" "$VULNDB_MEDIA" "$VULNDB_LOGS"

    local py3
    py3="$(command -v python3.12 || command -v python3)"

    # venv
    if [[ ! -d "$VULNDB_HOME/.venv" ]]; then
        sudo -u vulndb "$py3" -m venv "$VULNDB_HOME/.venv"
    fi
    sudo -u vulndb "$VULNDB_HOME/.venv/bin/pip" install -q -U pip
    sudo -u vulndb "$VULNDB_HOME/.venv/bin/pip" install -q -r "$VULNDB_HOME/requirements.txt"
    ok "venv и зависимости установлены"

    # .env
    if [[ ! -f "$VULNDB_HOME/.env" ]]; then
        sudo -u vulndb cp "$VULNDB_HOME/.env.example" "$VULNDB_HOME/.env"
        # Patch defaults for bare-metal layout
        sed -i \
            -e 's|@db:|@127.0.0.1:|g' \
            -e 's|redis://redis:|redis://127.0.0.1:|g' \
            -e 's|ENV_FILE_PATH=.*|ENV_FILE_PATH=/opt/vulndb/.env|' \
            -e 's|LICENSE_FILE=.*|LICENSE_FILE=/opt/vulndb/.novalic|' \
            "$VULNDB_HOME/.env"
        chmod 600 "$VULNDB_HOME/.env"
        ok ".env создан — отредактируйте пароли и SECRET_KEY"
    else
        ok ".env уже существует"
    fi

    # Migrations & static
    sudo -u vulndb "$VULNDB_HOME/.venv/bin/python" "$VULNDB_HOME/manage.py" migrate --noinput
    sudo -u vulndb "$VULNDB_HOME/.venv/bin/python" "$VULNDB_HOME/manage.py" collectstatic --noinput --clear 2>/dev/null || true
    ok "Миграции и статика готовы"
}

# ── 6. systemd ────────────────────────────────────────────
setup_systemd() {
    step "Установка systemd-юнитов"
    cp "$VULNDB_HOME/deploy/systemd/vulndb-web.service"    /etc/systemd/system/
    cp "$VULNDB_HOME/deploy/systemd/vulndb-worker.service" /etc/systemd/system/
    cp "$VULNDB_HOME/deploy/systemd/vulndb-beat.service"   /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable --now vulndb-web vulndb-worker vulndb-beat
    ok "Сервисы vulndb запущены"
}

# ── 7. Nginx ──────────────────────────────────────────────
setup_nginx() {
    step "Настройка Nginx"
    cp "$VULNDB_HOME/deploy/nginx/vulndb.conf" /etc/nginx/conf.d/vulndb.conf

    local hostname="${VULNDB_HOSTNAME:-$(hostname -f 2>/dev/null || echo localhost)}"
    sed -i "s/CHANGE_ME_HOSTNAME/${hostname}/" /etc/nginx/conf.d/vulndb.conf

    nginx -t || die "Ошибка конфигурации nginx"
    systemctl enable --now nginx
    systemctl reload nginx
    ok "Nginx настроен (server_name=$hostname)"
}

# ── 8. Firewall ───────────────────────────────────────────
setup_firewall() {
    step "Настройка firewalld"
    systemctl enable --now firewalld 2>/dev/null || true
    firewall-cmd --permanent --add-service=http  2>/dev/null || true
    firewall-cmd --permanent --add-service=https 2>/dev/null || true
    firewall-cmd --reload 2>/dev/null || true
    ok "firewalld настроен"
}

# ── main ──────────────────────────────────────────────────
main() {
    need_root
    install_packages
    setup_postgres
    create_db
    setup_redis
    setup_app
    setup_systemd
    setup_nginx
    setup_firewall

    echo ""
    ok "Установка VULNDB завершена!"
    echo ""
    echo "Следующие шаги:"
    echo "  1. Отредактируйте /opt/vulndb/.env (SECRET_KEY, пароль БД, лицензия)"
    echo "  2. sudo systemctl restart vulndb-web vulndb-worker vulndb-beat"
    echo "  3. Откройте https://$hostname/ для первоначальной настройки"
    echo ""
}

main "$@"
