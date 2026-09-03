#!/usr/bin/env bash
# =============================================================================
# VULNDB — установка стека и приложения (РЕД ОС 8 / RHEL-подобные: dnf)
#
# Пароль существующей УЗ postgres ЗНАТЬ НЕ НУЖНО.
# Скрипт заходит в PostgreSQL через peer:  sudo -u postgres psql
# и сам ЗАДАЁТ новые пароли (роль приложения, опционально суперпользователь
# postgres, веб-админ). В конце печатает все данные и пишет копию в файл.
#
#   sudo bash scripts/install-vulndb.sh
#
# Переменные (если заданы — вопросы не задаются):
#   VULNDB_DB_PASSWORD          пароль роли БД vulndb
#   VULNDB_POSTGRES_PASSWORD    пароль суперпользователя PostgreSQL (роль postgres)
#   VULNDB_ADMIN_USER           логин веб-админа (по умолчанию admin)
#   VULNDB_ADMIN_PASSWORD       пароль веб-админа
#   VULNDB_ADMIN_NAME           ФИО веб-админа
#   VULNDB_SECRET_KEY
#   VULNDB_DOMAIN
#   VULNDB_ASSUME_YES=1         без вопросов, пароли генерируются
# =============================================================================
set -euo pipefail

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m✔\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m✖ %s\033[0m\n' "$*" >&2; exit 1; }

[[ ${EUID:-$(id -u)} -eq 0 ]] || die "Запустите скрипт от root: sudo bash $0"

ASSUME_YES="${VULNDB_ASSUME_YES:-0}"
INSTALL_DIR="${VULNDB_INSTALL_DIR:-/opt/vulndb}"
DATA_DIR="${VULNDB_DATA_DIR:-/var/lib/vulndb}"
LOG_DIR="${VULNDB_LOG_DIR:-/var/log/vulndb}"
APP_USER="${VULNDB_USER:-vulndb}"
DB_NAME="${VULNDB_DB_NAME:-vulndb}"
DB_USER="${VULNDB_DB_USER:-vulndb}"
DB_PASSWORD="${VULNDB_DB_PASSWORD:-}"
PG_SUPER_PASSWORD="${VULNDB_POSTGRES_PASSWORD:-}"
ADMIN_USER="${VULNDB_ADMIN_USER:-admin}"
ADMIN_PASSWORD="${VULNDB_ADMIN_PASSWORD:-}"
ADMIN_NAME="${VULNDB_ADMIN_NAME:-}"
SECRET_KEY="${VULNDB_SECRET_KEY:-}"
DOMAIN="${VULNDB_DOMAIN:-}"
REPO_URL="${VULNDB_REPO_URL:-}"
SKIP_FIREWALL="${VULNDB_SKIP_FIREWALL:-0}"
SKIP_NGINX="${VULNDB_SKIP_NGINX:-0}"
PG_SERVICE=""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_SRC="$(cd "${SCRIPT_DIR}/.." && pwd)"
SRC_DIR="${VULNDB_SRC_DIR:-$DEFAULT_SRC}"

confirm() {
  local prompt="$1"
  if [[ "$ASSUME_YES" == "1" ]]; then
    return 0
  fi
  read -r -p "$prompt [y/N] " ans
  [[ "$ans" =~ ^[YyДд]$ ]]
}

rand_hex() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "${1:-24}"
  else
    head -c 64 /dev/urandom | tr -dc 'a-f0-9' | head -c "${1:-48}"
  fi
}

urlencode() {
  V="$1" python3 -c "from urllib.parse import quote; import os; print(quote(os.environ['V'], safe=''))"
}

set_role_password() {
  local role="$1" pw="$2"
  [[ "$role" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]] || die "Некорректное имя роли PostgreSQL: $role"
  DB_ROLE="$role" DB_PW="$pw" python3 - <<'PY'
import os, subprocess
role = os.environ["DB_ROLE"]
pw = os.environ["DB_PW"].replace("'", "''")
sql = "ALTER USER %s WITH PASSWORD '%s';" % (role, pw)
subprocess.check_call(["sudo", "-u", "postgres", "psql", "-v", "ON_ERROR_STOP=1", "-c", sql])
PY
}

prompt_line() {
  local prompt="$1" default="${2:-}"
  local val=""
  if [[ "$ASSUME_YES" == "1" ]] || [[ ! -t 0 ]]; then
    printf '%s' "$default"
    return
  fi
  if [[ -n "$default" ]]; then
    read -r -p "$prompt [$default]: " val || true
  else
    read -r -p "$prompt: " val || true
  fi
  printf '%s' "${val:-$default}"
}

prompt_password() {
  # $1 prompt, $2 allow empty-to-generate (1/0)
  local prompt="$1" allow_gen="${2:-1}"
  local a="" b=""
  if [[ "$ASSUME_YES" == "1" ]] || [[ ! -t 0 ]]; then
    if [[ "$allow_gen" == "1" ]]; then
      rand_hex 16
      return
    fi
    printf ''
    return
  fi
  while true; do
    if [[ "$allow_gen" == "1" ]]; then
      read -r -s -p "$prompt (пусто = сгенерировать): " a || true
    else
      read -r -s -p "$prompt: " a || true
    fi
    echo >&2
    if [[ -z "$a" && "$allow_gen" == "1" ]]; then
      a="$(rand_hex 16)"
      echo "  → сгенерирован" >&2
      printf '%s' "$a"
      return
    fi
    if [[ -z "$a" ]]; then
      echo "  пустой пароль не допускается" >&2
      continue
    fi
    read -r -s -p "  Повторите пароль: " b || true
    echo >&2
    if [[ "$a" != "$b" ]]; then
      echo "  не совпадают, ещё раз" >&2
      continue
    fi
    printf '%s' "$a"
    return
  done
}

detect_pkg() {
  if command -v dnf >/dev/null 2>&1; then
    echo dnf
  elif command -v yum >/dev/null 2>&1; then
    echo yum
  else
    die "Нужен dnf/yum (РЕД ОС / RHEL / CentOS / Rocky / Alma)."
  fi
}

# ---------- 0. Пароли (не нужен текущий пароль postgres) ----------
echo
echo "════════════════════════════════════════════════════════════"
echo " VULNDB — установка"
echo " Текущий пароль УЗ postgres знать не нужно."
echo " Скрипт зайдёт как:  sudo -u postgres psql  (peer)"
echo " и запишет НОВЫЕ пароли, которые покажет в конце."
echo "════════════════════════════════════════════════════════════"

if [[ ! -t 0 && "$ASSUME_YES" != "1" ]]; then
  warn "Нет TTY (например curl | sudo bash). Пароли будут сгенерированы."
  warn "Либо скачайте скрипт и запустите: sudo bash scripts/install-vulndb.sh"
  ASSUME_YES=1
fi

if [[ -z "$DOMAIN" ]]; then
  DOMAIN="$(prompt_line "Домен или IP для Nginx" "$(hostname -f 2>/dev/null || hostname || echo vulndb.local)")"
fi
if [[ -z "$DB_USER" ]]; then
  DB_USER="vulndb"
fi
DB_USER="$(prompt_line "Роль PostgreSQL приложения" "$DB_USER")"
DB_NAME="$(prompt_line "Имя базы" "$DB_NAME")"

if [[ -z "$DB_PASSWORD" ]]; then
  echo
  echo "Пароль роли ${DB_USER} (этим паролем ходит Django):"
  DB_PASSWORD="$(prompt_password "  Пароль БД ${DB_USER}" 1)"
fi

SET_PG_SUPER=1
if [[ -n "$PG_SUPER_PASSWORD" ]]; then
  SET_PG_SUPER=1
elif [[ "$ASSUME_YES" == "1" ]]; then
  PG_SUPER_PASSWORD="$(rand_hex 16)"
  SET_PG_SUPER=1
else
  echo
  if confirm "Задать пароль суперпользователя PostgreSQL (роль postgres), чтобы можно было входить по паролю?"; then
    PG_SUPER_PASSWORD="$(prompt_password "  Пароль роли postgres" 1)"
    SET_PG_SUPER=1
  else
    SET_PG_SUPER=0
    PG_SUPER_PASSWORD=""
  fi
fi

ADMIN_USER="$(prompt_line "Логин веб-администратора VULNDB" "$ADMIN_USER")"
if [[ -z "$ADMIN_PASSWORD" ]]; then
  echo
  echo "Пароль входа в веб-консоль (${ADMIN_USER}):"
  ADMIN_PASSWORD="$(prompt_password "  Пароль ${ADMIN_USER}" 1)"
fi
if [[ -z "$ADMIN_NAME" ]]; then
  ADMIN_NAME="$(prompt_line "ФИО администратора" "Администратор")"
fi

if [[ -z "$SECRET_KEY" ]]; then
  SECRET_KEY="$(rand_hex 32)"
fi

echo
ok "Пароли приняты. Установка пойдёт без запроса пароля postgres."

PKG="$(detect_pkg)"

# ---------- 1. Packages ----------
log "Установка системных пакетов ($PKG)"
$PKG -y install \
  git curl wget tar gzip \
  postgresql-server postgresql \
  redis \
  nginx firewalld \
  gcc gcc-c++ make libpq-devel \
  python3 python3-devel python3-pip \
  || warn "Часть пакетов могла не установиться — проверьте имена в репозитории РЕД ОС."

PYTHON_BIN="python3"
if command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN="python3.12"
  $PKG -y install python3.12 python3.12-devel 2>/dev/null || true
fi
ok "Python: $($PYTHON_BIN --version 2>&1)"

# ---------- 2. PostgreSQL ----------
log "Инициализация PostgreSQL"

pg_cluster_ready() {
  find /var/lib/pgsql /var/lib/postgresql -name PG_VERSION 2>/dev/null | grep -q .
}

init_postgres_cluster() {
  if pg_cluster_ready; then
    return 0
  fi
  if command -v postgresql-setup >/dev/null 2>&1; then
    postgresql-setup --initdb || /usr/bin/postgresql-setup --initdb || true
  fi
  local setup
  for setup in /usr/pgsql-*/bin/postgresql-*-setup /usr/bin/postgresql-*-setup; do
    [[ -x "$setup" ]] || continue
    "$setup" initdb || true
    pg_cluster_ready && return 0
  done
  pg_cluster_ready
}

start_postgres() {
  systemctl daemon-reload 2>/dev/null || true
  local names=()
  local unit
  while read -r unit _; do
    [[ "$unit" =~ ^postgresql([.-][0-9]+)?\.service$ ]] && names+=("${unit%.service}")
  done < <(systemctl list-unit-files --type=service --no-legend 2>/dev/null || true)
  names+=(postgresql-16 postgresql-15 postgresql-14 postgresql)
  local seen="" svc
  for svc in "${names[@]}"; do
    [[ -n "$svc" ]] || continue
    [[ " $seen " == *" $svc "* ]] && continue
    seen+=" $svc"
    if systemctl enable --now "$svc" 2>/dev/null; then
      PG_SERVICE="$svc"
      return 0
    fi
  done
  return 1
}

restart_postgres() {
  if [[ -n "${PG_SERVICE:-}" ]]; then
    systemctl restart "$PG_SERVICE" 2>/dev/null && return 0
  fi
  systemctl restart postgresql-16 2>/dev/null || systemctl restart postgresql 2>/dev/null || \
    systemctl restart postgresql-15 2>/dev/null || true
}

init_postgres_cluster || warn "initdb мог не выполниться — проверьте каталог данных PostgreSQL"
if ! start_postgres; then
  warn "Доступные unit-файлы PostgreSQL:"
  systemctl list-unit-files --type=service --no-legend 2>/dev/null | grep -i postgres || true
  die "Не удалось запустить PostgreSQL (ожидались postgresql / postgresql-16). Смотрите: journalctl -u postgresql* -e"
fi
ok "PostgreSQL service: ${PG_SERVICE}"

PG_HBA="$(find /var/lib/pgsql /var/lib/pgsql/*/data /var/lib/postgresql -name pg_hba.conf 2>/dev/null | head -n1 || true)"
if [[ -n "$PG_HBA" ]]; then
  if ! grep -q 'vulndb install' "$PG_HBA"; then
    tmp="$(mktemp)"
    cat > "$tmp" <<'HBA'
# vulndb install — peer для ОС-пользователя postgres (sudo -u postgres psql без пароля)
local   all             postgres                                peer
local   all             all                                     scram-sha-256
host    all             all             127.0.0.1/32            scram-sha-256
host    all             all             ::1/128                 scram-sha-256

HBA
    cat "$PG_HBA" >> "$tmp"
    mv "$tmp" "$PG_HBA"
    chown postgres:postgres "$PG_HBA" 2>/dev/null || true
    chmod 600 "$PG_HBA" 2>/dev/null || true
  fi
  restart_postgres
  ok "pg_hba: $PG_HBA  (postgres — peer, остальные — пароль)"
else
  warn "pg_hba.conf не найден автоматически."
fi

[[ "$DB_USER" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]] || die "Имя роли БД должно быть идентификатором: буквы, цифры, _"
[[ "$DB_NAME" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]] || die "Имя БД должно быть идентификатором: буквы, цифры, _"

log "Создание роли и БД PostgreSQL ($DB_USER / $DB_NAME) — пароль задаём мы"
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE USER ${DB_USER} LOGIN;
  END IF;
END
\$\$;
SQL
set_role_password "$DB_USER" "$DB_PASSWORD"

if [[ "$SET_PG_SUPER" == "1" && -n "$PG_SUPER_PASSWORD" ]]; then
  set_role_password postgres "$PG_SUPER_PASSWORD"
  ok "Пароль роли postgres задан (TCP: psql -h 127.0.0.1 -U postgres)"
fi

DB_EXISTS="$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" || true)"
if [[ "$DB_EXISTS" != "1" ]]; then
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER} ENCODING 'UTF8';"
fi
sudo -u postgres psql -v ON_ERROR_STOP=1 -d "$DB_NAME" <<SQL
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
GRANT ALL ON SCHEMA public TO ${DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ${DB_USER};
SQL

if PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" -c 'SELECT 1;' >/dev/null; then
  ok "PostgreSQL: SELECT 1 OK (${DB_USER}@127.0.0.1/${DB_NAME})"
else
  die "Не удалось подключиться к PostgreSQL под ${DB_USER} с заданным паролем"
fi

# ---------- 3. Redis ----------
log "Настройка Redis"
systemctl enable --now redis 2>/dev/null || systemctl enable --now redis-server 2>/dev/null || \
  die "Не удалось запустить Redis"
if redis-cli PING | grep -qi PONG; then
  ok "Redis: PONG"
else
  warn "redis-cli PING не вернул PONG — проверьте сервис redis"
fi

# ---------- 4. OS user & dirs ----------
log "Пользователь и каталоги приложения"
id "$APP_USER" >/dev/null 2>&1 || useradd --system --home "$INSTALL_DIR" --shell /sbin/nologin "$APP_USER"
mkdir -p "$INSTALL_DIR" "$DATA_DIR/media" "$LOG_DIR"
chown -R "$APP_USER:$APP_USER" "$INSTALL_DIR" "$DATA_DIR" "$LOG_DIR"

# ---------- 5. Application code ----------
log "Размещение кода в $INSTALL_DIR"
if [[ -f "$INSTALL_DIR/manage.py" ]]; then
  ok "Код уже есть в $INSTALL_DIR"
elif [[ -f "$SRC_DIR/manage.py" ]]; then
  log "Копирование из $SRC_DIR → $INSTALL_DIR"
  rsync -a --delete \
    --exclude '.git' --exclude '.venv' --exclude 'db.sqlite3' \
    --exclude 'staticfiles' --exclude 'media' --exclude '__pycache__' \
    "$SRC_DIR"/ "$INSTALL_DIR"/
elif [[ -n "$REPO_URL" ]]; then
  log "git clone $REPO_URL"
  sudo -u "$APP_USER" git clone "$REPO_URL" "$INSTALL_DIR"
else
  die "Не найден manage.py. Укажите VULNDB_SRC_DIR или VULNDB_REPO_URL."
fi
chown -R "$APP_USER:$APP_USER" "$INSTALL_DIR"

# ---------- 6. venv + deps ----------
log "Python venv и зависимости"
if [[ ! -d "$INSTALL_DIR/.venv" ]]; then
  sudo -u "$APP_USER" "$PYTHON_BIN" -m venv "$INSTALL_DIR/.venv"
fi
sudo -u "$APP_USER" "$INSTALL_DIR/.venv/bin/pip" install -U pip wheel
sudo -u "$APP_USER" "$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
ok "Зависимости установлены"

# ---------- 7. .env ----------
log "Файл .env"
if [[ -z "$DOMAIN" ]]; then
  DOMAIN="$(hostname -f 2>/dev/null || hostname || echo vulndb.local)"
fi
PRIMARY_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
ALLOWED_HOSTS="${DOMAIN},localhost,127.0.0.1"
[[ -n "$PRIMARY_IP" ]] && ALLOWED_HOSTS="${ALLOWED_HOSTS},${PRIMARY_IP}"

DB_PASSWORD_ENC="$(urlencode "$DB_PASSWORD")"
DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD_ENC}@127.0.0.1:5432/${DB_NAME}"
ENV_FILE="$INSTALL_DIR/.env"
WRITE_ENV=1

if [[ -f "$ENV_FILE" ]] && [[ "$ASSUME_YES" != "1" ]]; then
  if ! confirm ".env уже существует — перезаписать новыми паролями?"; then
    WRITE_ENV=0
    warn "Оставляем существующий .env"
  fi
fi

if [[ "$WRITE_ENV" == "1" ]]; then
  cat > "$ENV_FILE" <<EOF
DEBUG=0
SECRET_KEY=${SECRET_KEY}
ALLOWED_HOSTS=${ALLOWED_HOSTS}
CSRF_TRUSTED_ORIGINS=https://${DOMAIN},http://${DOMAIN},http://127.0.0.1,http://localhost
TIME_ZONE=Europe/Moscow

DATABASE_URL=${DATABASE_URL}
DB_SSLMODE=prefer

REDIS_URL=redis://127.0.0.1:6379/0
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0

VULNDB_LICENSE_REQUIRED=0
LICENSE_SERVER_URL=http://127.0.0.1:8090
LICENSE_FILE=${INSTALL_DIR}/.novalic
LICENSE_GRACE_DAYS=14
ENV_FILE_PATH=${ENV_FILE}

EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=vulndb@${DOMAIN}
EOF
  chown "$APP_USER:$APP_USER" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  ok ".env записан ($ENV_FILE)"
fi

# ---------- 8. migrate / static / admin ----------
log "Миграции и collectstatic"
cd "$INSTALL_DIR"
run_manage() {
  sudo -u "$APP_USER" bash -lc "
    set -a
    # shellcheck disable=SC1091
    source '$ENV_FILE'
    set +a
    cd '$INSTALL_DIR'
    exec '$INSTALL_DIR/.venv/bin/python' manage.py \"\$@\"
  " -- "$@"
}
run_manage migrate --noinput
run_manage collectstatic --noinput
mkdir -p "$DATA_DIR/media"
if [[ ! -e "$INSTALL_DIR/media" ]]; then
  ln -s "$DATA_DIR/media" "$INSTALL_DIR/media"
fi
chown -R "$APP_USER:$APP_USER" "$DATA_DIR/media"
ok "migrate + collectstatic"

if [[ -n "$ADMIN_USER" && -n "$ADMIN_PASSWORD" ]]; then
  log "Веб-администратор ${ADMIN_USER}"
  sudo -u "$APP_USER" env \
    VULNDB_BOOTSTRAP_USER="$ADMIN_USER" \
    VULNDB_BOOTSTRAP_PASSWORD="$ADMIN_PASSWORD" \
    VULNDB_BOOTSTRAP_NAME="$ADMIN_NAME" \
    bash -lc "
      set -a
      source '$ENV_FILE'
      set +a
      cd '$INSTALL_DIR'
      '$INSTALL_DIR/.venv/bin/python' - <<'PY'
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from vulndb.apps.accounts.models import Role, User
username = os.environ['VULNDB_BOOTSTRAP_USER']
password = os.environ['VULNDB_BOOTSTRAP_PASSWORD']
name = os.environ.get('VULNDB_BOOTSTRAP_NAME') or ''
u, created = User.objects.get_or_create(
    username=username,
    defaults={'full_name': name, 'role': Role.PLATFORM_ADMIN, 'is_staff': True, 'is_superuser': True},
)
u.full_name = name or u.full_name
u.role = Role.PLATFORM_ADMIN
u.is_staff = True
u.is_superuser = True
u.is_active = True
u.set_password(password)
u.save()
print('created' if created else 'updated', username)
PY
    "
  ok "Веб-админ ${ADMIN_USER} готов (роль Platform Admin)"
fi

# ---------- 9. systemd ----------
log "systemd unit-файлы"
for unit in vulndb-web vulndb-worker vulndb-beat; do
  src="$INSTALL_DIR/deploy/systemd/${unit}.service"
  [[ -f "$src" ]] || die "Нет файла $src"
  sed "s|/opt/vulndb|${INSTALL_DIR}|g" "$src" > "/etc/systemd/system/${unit}.service"
done
systemctl daemon-reload
systemctl enable --now vulndb-web vulndb-worker vulndb-beat
sleep 2
systemctl is-active --quiet vulndb-web && ok "vulndb-web active" || warn "vulndb-web не active — journalctl -u vulndb-web"
systemctl is-active --quiet vulndb-worker && ok "vulndb-worker active" || warn "vulndb-worker не active"
systemctl is-active --quiet vulndb-beat && ok "vulndb-beat active" || warn "vulndb-beat не active"

# ---------- 10. Nginx ----------
if [[ "$SKIP_NGINX" != "1" ]]; then
  log "Nginx reverse proxy"
  NGINX_SRC="$INSTALL_DIR/deploy/nginx/vulndb.conf"
  NGINX_DST="/etc/nginx/conf.d/vulndb.conf"
  sed -e "s/CHANGE_ME_HOSTNAME/${DOMAIN}/g" \
      -e "s|/opt/vulndb|${INSTALL_DIR}|g" \
      -e "s|/var/lib/vulndb/media|${DATA_DIR}/media|g" \
      "$NGINX_SRC" > "$NGINX_DST"
  if command -v getenforce >/dev/null 2>&1 && [[ "$(getenforce)" == "Enforcing" ]]; then
    command -v semanage >/dev/null 2>&1 && {
      semanage fcontext -a -t httpd_sys_content_t "${INSTALL_DIR}/staticfiles(/.*)?" 2>/dev/null || true
      semanage fcontext -a -t httpd_sys_rw_content_t "${DATA_DIR}/media(/.*)?" 2>/dev/null || true
      restorecon -Rv "${INSTALL_DIR}/staticfiles" "${DATA_DIR}/media" 2>/dev/null || true
      setsebool -P httpd_can_network_connect 1 2>/dev/null || true
    }
  fi
  nginx -t
  systemctl enable --now nginx
  systemctl reload nginx
  ok "Nginx: http://${DOMAIN}/"
fi

# ---------- 11. Firewall ----------
if [[ "$SKIP_FIREWALL" != "1" ]] && command -v firewall-cmd >/dev/null 2>&1; then
  log "firewalld: http/https"
  systemctl enable --now firewalld 2>/dev/null || true
  firewall-cmd --permanent --add-service=http || true
  firewall-cmd --permanent --add-service=https || true
  firewall-cmd --reload || true
  ok "firewalld обновлён"
fi

# ---------- 12. Health ----------
log "Проверка /healthz"
sleep 1
if curl -fsS "http://127.0.0.1:8000/healthz" >/dev/null 2>&1 || \
   curl -fsS "http://127.0.0.1/healthz" >/dev/null 2>&1; then
  ok "healthz = ok"
else
  warn "healthz пока не отвечает — смотрите: journalctl -u vulndb-web -n 50"
fi

CRED_FILE="/root/vulndb-install-credentials.txt"
PG_PASS_LINE="(не задавали — вход: sudo -u postgres psql)"
if [[ "$SET_PG_SUPER" == "1" && -n "$PG_SUPER_PASSWORD" ]]; then
  PG_PASS_LINE="$PG_SUPER_PASSWORD"
fi

cat > "$CRED_FILE" <<EOF
VULNDB — данные установки  $(date -Iseconds)
================================================
URL (браузер)     : http://${DOMAIN}/
Мастер /setup/    : http://${DOMAIN}/setup/
По IP             : http://${PRIMARY_IP:-}/

Веб-консоль
  логин           : ${ADMIN_USER}
  пароль          : ${ADMIN_PASSWORD}
  роль            : Platform Admin
  пользователи    : http://${DOMAIN}/users/  (только админ)

PostgreSQL
  host/port       : 127.0.0.1:5432
  database        : ${DB_NAME}
  user (приложение): ${DB_USER}
  password        : ${DB_PASSWORD}
  суперuser postgres password : ${PG_PASS_LINE}
  без пароля      : sudo -u postgres psql
  проверка        : PGPASSWORD='${DB_PASSWORD}' psql -h 127.0.0.1 -U ${DB_USER} -d ${DB_NAME} -c 'SELECT 1'

Redis             : 127.0.0.1:6379
.env              : ${ENV_FILE}
SECRET_KEY        : ${SECRET_KEY}
Install dir       : ${INSTALL_DIR}
systemd           : vulndb-web vulndb-worker vulndb-beat
PostgreSQL unit   : ${PG_SERVICE}

Команды:
  systemctl status vulndb-web vulndb-worker vulndb-beat
  journalctl -u vulndb-web -f
================================================
Файл только для root (chmod 600). Не коммитьте.
EOF
chmod 600 "$CRED_FILE"

echo
echo "════════════════════════════════════════════════════════════"
echo " VULNDB установлен. Сохраните эти данные:"
echo "════════════════════════════════════════════════════════════"
echo "  URL            : http://${DOMAIN}/   (мастер: /setup/)"
echo "  Веб-админ      : ${ADMIN_USER}"
echo "  Пароль веба    : ${ADMIN_PASSWORD}"
echo "  Пользователи   : http://${DOMAIN}/users/  (только админ)"
echo
echo "  PostgreSQL"
echo "    host         : 127.0.0.1:5432"
echo "    db / user    : ${DB_NAME} / ${DB_USER}"
echo "    password     : ${DB_PASSWORD}"
echo "    postgres     : ${PG_PASS_LINE}"
echo "    без пароля   : sudo -u postgres psql"
echo
echo "  Redis          : 127.0.0.1:6379"
echo "  .env           : ${ENV_FILE}"
echo "  Копия          : ${CRED_FILE}"
echo "  Логи           : journalctl -u vulndb-web -f"
echo "════════════════════════════════════════════════════════════"
ok "Установка VULNDB завершена"
echo
echo "Дальше: откройте http://${DOMAIN}/setup/ (организация → источники → админ уже создан)."
echo "Локальных пользователей с ролями создаёт администратор в разделе «Пользователи»."
