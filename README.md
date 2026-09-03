# VULNDB

Локальная **Vulnerability Database**: каталог уязвимостей (NVD + CISA KEV + БДУ ФСТЭК + внутренние ID), заявки на устранение, лицензирование, мастер настройки и уведомления.

Это **не** TIP / threat-intelligence портал — продукт называется **VULNDB**. Wiki в составе нет.

UI-эталон: каталог [`novatip-ui/`](novatip-ui/) (стилистика enterprise-консоли перенесена в Django-шаблоны).

## Быстрый старт (Docker Compose)

```bash
cp .env.example .env
# при необходимости отредактируйте SECRET_KEY и POSTGRES_PASSWORD
docker compose up --build
```

Откройте http://localhost:8000/ — при первом запуске откроется **мастер настройки** (`/setup/`).

Сервисы Compose: `web`, `db` (PostgreSQL 16), `redis`, `worker`, `beat`, `license_server`.

Подробнее: [docs/DOCKER_DEV.md](docs/DOCKER_DEV.md).

## Локально без Docker (SQLite для разработки)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# оставьте DATABASE_URL пустым — будет SQLite
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

## Установка с нуля (ВМ → РЕД ОС 8 → VULNDB)

Пошаговый runbook для новичка:

1. [docs/00_OVERVIEW.md](docs/00_OVERVIEW.md) — архитектура  
2. [docs/01_VM_AND_OS.md](docs/01_VM_AND_OS.md) — ВМ и установка РЕД ОС 8  
3. [docs/02_STACK_INSTALL.md](docs/02_STACK_INSTALL.md) — PostgreSQL, Redis, Python, Nginx  
4. [docs/03_APP_INSTALL.md](docs/03_APP_INSTALL.md) — приложение, systemd, TLS  
5. [docs/04_WIZARD_AND_FIRST_LOGIN.md](docs/04_WIZARD_AND_FIRST_LOGIN.md) — мастер и первый вход  
6. [docs/05_OPERATIONS.md](docs/05_OPERATIONS.md) — бэкап, обновление, типовые ошибки  
7. [docs/DEPLOY_REDOS8.md](docs/DEPLOY_REDOS8.md) — сводный чеклист  

## Стек

| Компонент | Выбор |
|---|---|
| Backend | Python 3.12+, Django 5 |
| UI | Django templates + HTMX + Alpine.js (vendor локально, без CDN) |
| БД | PostgreSQL 16 |
| Очереди | Redis 7 + Celery + Celery Beat |
| WSGI | Gunicorn |
| License | Ed25519, файл `.novalic`, online heartbeat + offline grace 14 дней |

## Основные маршруты

| URL | Назначение |
|---|---|
| `/accounts/login/` | Вход |
| `/` | Дашборд |
| `/vulns/` | Каталог |
| `/vulns/<id>/` | Карточка (NVD↔BDU, блок CVSS) |
| `/tickets/` | Заявки |
| `/setup/` | Мастер первичной настройки |
| `/settings/` | Настройки (вкладки, включая `#sync`) |
| `/healthz` | Healthcheck |

## Переменные окружения

См. [`.env.example`](.env.example). Секреты в git не коммитятся.

## Структура

```text
vulndb/apps/
  core/        # SystemSettings, wizard, branding, health
  licensing/   # клиент лицензии, fingerprint, grace
  vulns/       # NVD/KEV/BDU/local-ID, карточки, sync
  tickets/     # заявки, SLA, переходы статусов
  notify/      # email + telegram
  accounts/    # пользователи, роли
  audit/       # журнал
license_server/  # минимальный сервис вендора
novatip-ui/      # HTML/CSS прототипы UI (эталон)
```

## Лицензия разработки

В `DEBUG=1` допускается демо-лицензия. Для боевого контура загрузите `.novalic` в мастере или через License Server (`license_server/`).

## Запреты продукта

- Нет Wiki / knowledge-base  
- Нет CDN для JS/CSS  
- Нет саморегистрации  
- Секреты и `.novalic` не хранятся в репозитории  
