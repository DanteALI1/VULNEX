# Промпт: собрать NovaTIP как веб-приложение и выложить на GitHub

Скопируй этот документ целиком в новый чат Cursor / Claude / другого coding-агента.  
Цель агента: **реализовать рабочее веб-приложение NovaTIP**, использовать HTML/CSS-прототипы как эталон UI, создать **git-репозиторий** и **запушить на GitHub**.

---

## Роль и результат

Ты — senior full-stack инженер (Django + security products UI).  
Собери продукт **NovaTIP** (Threat Intelligence Platform): локальный каталог уязвимостей (NVD + KEV + БДУ ФСТЭК + внутренние ID), заявки на устранение, лицензирование, мастер настройки, уведомления.

**Wiki / NovaWIKI в продукте НЕТ — не реализовывать.**

Итоговый артефакт:
1. Полный исходный код в корне репозитория.
2. README с быстрым стартом (Docker Compose для dev + runbook для РЕД ОС 8).
3. Публичный или приватный репозиторий на GitHub (`gh repo create` + `git push -u origin main`).
4. UI визуально и структурно соответствует прототипам (см. ниже), не «типовой AI purple landing».

---

## Эталон UI (обязательно)

Если в workspace есть каталог `novatip-ui/` — **это source of truth по вёрстке**. Перенеси стили и структуру экранов в Django templates:

| Прототип | Маршрут приложения |
|---|---|
| `login.html` | `/accounts/login/` |
| `dashboard.html` | `/` |
| `vulns.html` | `/vulns/` |
| `vuln-detail.html` | `/vulns/<id>/` |
| `tickets.html` | `/tickets/` |
| `setup-*.html` | `/setup/` (wizard) |
| `settings.html` | `/settings/` (вкладки, включая sync) |
| `css/tip-console.css` | `static/css/tip-console.css` |
| `js/tip-ui.js` | `static/js/tip-ui.js` |

Стиль: enterprise VM-консоль (класс MaxPatrol VM) — тёмный сайдбар, светлый холст, плотные таблицы, синий акцент `#0a7ab8`, без CDN, без Inter/фиолетовых градиентов.

### Ключевые UX-решения (уже согласованы)

1. **Login** — слева логотип компании + текст (из мастера/настроек) + CSS-анимация «cyber» (сетка, scan-line, hex, nodes). Без саморегистрации.
2. **Дашборд** — KPI Critical/High/KEV/локальные ID, источники sync, таблицы «требуют внимания» и заявки.
3. **Каталог** — расширенные фильтры в **сворачиваемой** панели + чипы активных условий; типы записей CVE / BDU / локальные `{PREFIX}-…`.
4. **Карточка уязвимости — одна страница**:
   - шапка: ID, max severity, бейджи KEV / BDU / LOCAL;
   - описание с переключателем **NVD ↔ BDU** (не отдельные «простыни» вкладок);
   - **отдельный блок «Метрики CVSS»** на той же странице с переключением версий **3.1 / 3.0 / 2.0 / 4.0**;
   - CWE, CPE, references, связанные заявки, история — на этой же странице.
5. **Заявки** — статусы и права зашиты в систему (см. § Заявки).
6. **Мастер** — адаптивный (горизонтальный скролл шагов), шаги включают **Организация (префикс ID)** и **Оформление (логотип + тексты login)**.
7. **Настройки** — разделы **вкладками**, не одной длинной страницей. Пункт **Синхронизации** живёт внутри настроек (`/settings/#sync`), не отдельным пунктом главного меню.
8. Главное меню: Дашборд · Уязвимости · Заявки · Настройки. Wiki нет.

---

## Стек (зафиксирован)

| Компонент | Выбор |
|---|---|
| Backend | Python 3.12+, Django 5 |
| UI | Django templates + HTMX + Alpine.js (**vendor локально**, без CDN) |
| БД | PostgreSQL 16 |
| Очереди | Redis 7 + Celery + Celery Beat |
| WSGI | Gunicorn |
| Dev | Docker Compose (web, db, redis, worker, beat) |
| Prod target | РЕД ОС 8: Nginx + TLS + systemd |
| License | Ed25519, файл `.novalic`, online heartbeat + offline grace 14 дней |

Структура приложений:

```text
novatip/
  apps/
    core/        # SystemSettings, wizard, branding, health
    licensing/   # клиент лицензии, fingerprint, grace
    vulns/       # NVD/KEV/BDU/local-ID, карточки, sync
    tickets/     # заявки, SLA, переходы статусов
    notify/      # email + telegram
    accounts/    # пользователи, роли
    audit/       # журнал
  license_server/  # отдельный сервис вендора (можно monorepo sibling)
```

Секреты только в `.env` / GitHub Secrets. В репозитории — `.env.example`.

---

## Локальные ID уязвимостей

- В мастере и в настройках админ задаёт **префикс** (латиница/цифры, 2–16), например `ACME`.
- Запрещены зарезервированные префиксы: `CVE`, `BDU`.
- Формат внутренних карточек: `{PREFIX}-YYYY-NNNN` (автоинкремент по году).
- Внешние записи сохраняют канон: `CVE-…`, при необходимости `BDU:…`.
- Одна карточка = NVD-канон; KEV и BDU — обогащение, не дубликаты в списке при наличии CVE.
- BDU без CVE — отдельная карточка; при появлении CVE — merge.

NVD API 2.0 — канон полей и raw JSONB. Sync с **checkpoint/resume**. KEV из JSON CISA. BDU из XLSX ФСТЭК.

---

## Заявки (обязательная бизнес-логика)

Жизненный цикл:

`new → triage → in_progress → waiting → resolved → closed`  
(+ `rejected` из `new`/`triage`)

| Переход | Кто | Условие |
|---|---|---|
| Создать | analyst, admin | связь с уязвимостью, приоритет |
| Назначить исполнителя | analyst, admin | роль `ticket_assignee` |
| triage → in_progress | assignee (принять) / analyst | исполнитель назначен |
| in_progress ↔ waiting | assignee | причина ожидания |
| → resolved | **только исполнитель** (или admin) | описание устранения обязательно |
| resolved → closed | **постановщик или verifier** (не исполнитель) | явное подтверждение |
| resolved → in_progress | постановщик / verifier | причина возврата |
| → rejected | analyst из new/triage | причина |
| Force close | только `platform_admin` | причина + audit |

Исполнитель **не может** сам закрыть заявку. UI показывает только доступные действия для текущей роли. История статусов в timeline. Уведомления email/Telegram на события.

Роли: `platform_admin`, `analyst`, `ticket_assignee`, `verifier` (может быть флаг на профиле analyst).

---

## Мастер настройки (порядок)

При `setup_completed=false` все URL (кроме static/health) → `/setup/`.

1. Лицензия (`.novalic`, URL License Server, fingerprint, тест online)  
2. Организация (имя + **префикс локальных ID** + превью `ACME-2026-0001`)  
3. Оформление (логотип, заголовок/текст login)  
4. **База данных (обязательный рабочий шаг — не «только статус»)** — см. § ниже  
5. Администратор приложения (логин/ФИО/email/пароль NovaTIP)  
6. Источники (NVD key, KEV, BDU, расписание)  
7. Почта (тест)  
8. Telegram (тест / пропуск)  
9. Финиш → миграции если ещё не применены → kickoff NVD sync → дашборд  

Позже всё редактируется во вкладках `/settings/` (включая параметры БД только для просмотра/теста; смена пароля БД — с записью в защищённый `.env` и аудитом).

### Шаг «База данных» в мастере — подробно

Администратор площадки **должен создать учётную запись PostgreSQL и выдать права**, либо мастер помогает это сделать. Два режима на одном экране:

#### Режим A — «Подключиться к существующей БД» (типовой после runbook)

Поля формы:
- Host (по умолчанию `127.0.0.1`)
- Port (`5432`)
- Имя базы (`novatip`)
- **Имя пользователя БД** (УЗ PostgreSQL, не путать с админом NovaTIP)
- **Пароль УЗ БД**
- SSL/режим подключения (disable / prefer / require)

Кнопки:
- **«Проверить подключение»** — `SELECT 1`, проверка прав на CREATE/таблицы
- **«Сохранить и продолжить»** — записать `DATABASE_URL` в `.env` (или защищённый settings store), выполнить `migrate` если схема пустая

Показать понятные ошибки по-русски (неверный пароль, нет БД, нет прав, PostgreSQL не запущен).

#### Режим B — «Создать УЗ и базу» (для тех, кто ещё не создал роль)

Поля суперпользователя PostgreSQL (одноразово, **не сохранять** в настройки приложения):
- Host / Port
- Superuser (часто `postgres`) + пароль
- Имя новой БД
- Имя новой УЗ (например `novatip`)
- Пароль новой УЗ (с генератором и политикой сложности)
- Checkbox: «Создать БД + роль и выдать права»

По кнопке **«Создать УЗ и выдать права»** мастер выполняет (через `psycopg`, от имени superuser) эквивалент:

```sql
CREATE USER novatip WITH PASSWORD '...';
CREATE DATABASE novatip OWNER novatip ENCODING 'UTF8';
GRANT ALL PRIVILEGES ON DATABASE novatip TO novatip;
-- после connect к novatip:
GRANT ALL ON SCHEMA public TO novatip;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO novatip;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO novatip;
```

Затем автоматически проверяет вход уже под новой УЗ, сохраняет `DATABASE_URL`, предлагает Continue.

**Важно в UI и docs:**  
- УЗ PostgreSQL ≠ пользователь веб-интерфейса NovaTIP.  
- Пароль `postgres` / superuser **не хранить** после шага.  
- В Docker Compose для dev роль/БД создаются init-скриптом; мастер в compose-режиме может только «проверить и продолжить».  
- В production на РЕД ОС 8 runbook § ниже описывает создание УЗ вручную **и** через мастер.

---

## Документация деплоя «с нуля» (обязательный артефакт)

Целевая аудитория README/docs: **человек, который не умеет ставить ОС и ПО на ВМ**.  
Агент **обязан** написать подробный пошаговый runbook на русском:

### Файлы

| Файл | Содержание |
|---|---|
| `README.md` | Кратко: что это, ссылки на docs, Docker за 5 минут |
| `docs/00_OVERVIEW.md` | Архитектура одной картинкой, что куда ставится |
| `docs/01_VM_AND_OS.md` | ВМ → установка РЕД ОС 8 → сеть → обновления |
| `docs/02_STACK_INSTALL.md` | PostgreSQL, Redis, Python, Nginx, firewall, SELinux |
| `docs/03_APP_INSTALL.md` | Клон/копия NovaTIP, venv, .env, systemd, TLS |
| `docs/04_WIZARD_AND_FIRST_LOGIN.md` | Мастер, в т.ч. создание УЗ БД и прав |
| `docs/05_OPERATIONS.md` | Бэкап, обновление, логи, типичные ошибки |
| `docs/DEPLOY_REDOS8.md` | Сводный чеклист (можно оглавление + ссылки на 01–05) |
| `docs/DOCKER_DEV.md` | Локальная разработка через Compose |

Каждый файл — **нумерованные пункты**, готовые команды `bash` (copy-paste), ожидаемый вывод, что делать если ошибка.

### Минимальное содержание `docs/01_VM_AND_OS.md`

1. Что такое ВМ; рекомендуемые параметры (vCPU/RAM/диск/сеть) — таблица.  
2. Создание ВМ в **VMware ESXi / Hyper-V / VirtualBox** (кратко по шагам для каждого или «выбери гипервизор» + детально один основной: ESXi + VirtualBox).  
3. Скачивание ISO РЕД ОС 8, подключение к ВМ.  
4. Установка ОС: язык, разметка диска (рекомендуемая схема `/`, `/var`, `/opt` или одна `/` для новичка + предупреждение), hostname, root/пароль, сеть (DHCP или статический IP — оба варианта).  
5. Первый вход, `dnf update`, NTP (`chrony`), hostname.  
6. Создание обычного пользователя с `sudo`, вход по SSH с Windows (PuTTY / Windows Terminal).  
7. Открытие/проверка сети: ping шлюза, DNS.

### Минимальное содержание `docs/02_STACK_INSTALL.md`

1. Установка пакетов (`dnf`) с актуальными именами под РЕД ОС 8; примечание «если имя пакета другое — как найти».  
2. **PostgreSQL с нуля:** initdb, enable/start, **создание УЗ и БД**, `GRANT`, `pg_hba.conf` (localhost scram/md5), restart, проверка `psql`.  
3. Redis: bind localhost, пароль, enable/start, `PING`.  
4. Python 3.12+, build deps.  
5. Nginx установка (конфиг позже).  
6. firewalld: http/https, reload.  
7. SELinux: getenforce; базовые fcontext для static/media.

### Минимальное содержание `docs/03_APP_INSTALL.md`

1. Пользователь ОС `novatip`, каталоги `/opt/novatip`, `/var/lib/novatip`, `/var/log/novatip`.  
2. Получение кода с GitHub (`git clone`) или копирование release-архива.  
3. venv + `pip install -r requirements.txt`.  
4. Заполнение `.env` по `.env.example` (каждое поле объяснить простым языком).  
5. `migrate`, `collectstatic`.  
6. systemd unit-файлы (web, worker, beat) — полные примеры.  
7. Nginx reverse proxy + TLS (self-signed для лаборатории + Let’s Encrypt/внутренний CA для прод).  
8. Проверка `curl https://…/healthz`.

### Минимальное содержание `docs/04_WIZARD_AND_FIRST_LOGIN.md`

1. Открыть браузер на URL.  
2. Пройти мастер пошагово со скриншотами-описаниями (можно ASCII/описание блоков).  
3. **Отдельный подраздел: подключение БД** — когда использовать режим A vs B; как создать УЗ вручную в `psql`, если мастер не смог; таблица нужных прав.  
4. Создание администратора NovaTIP.  
5. Что делать после финиша (sync NVD, где смотреть прогресс).

### Тон документации

- Пиши для новичка: «открой терминал», «вставь команду», «если видишь ошибку X — значит Y».  
- Не предполагай знание Linux.  
- Все пароли — плейсхолдеры `CHANGE_ME_*`.  
- В конце каждого раздела — мини-чеклист «готово, если…».

---

## GitHub: что сделать агенту в конце

1. `git init` (если ещё нет), `.gitignore` для Python/Django/Node/env/media/staticfiles.
2. Коммиты логичные (каркас → apps → UI → docker → **docs runbook**), сообщения единообразно.
3. Создать репозиторий:
   ```bash
   gh repo create NovaTIP --private --source=. --remote=origin --description "Threat Intelligence Platform (NVD/KEV/BDU, tickets, licensing)"
   git push -u origin main
   ```
   Если `gh` недоступен — инструкции в README: создать пустой repo на GitHub и `git remote add` + push.
4. В README указать:
   - что это NovaTIP;
   - `docker compose up` для локального запуска;
   - переменные `.env.example`;
   - **ссылку «Установка с нуля (ВМ → ОС → NovaTIP)»** на `docs/01_VM_AND_OS.md` / оглавление;
   - UI-прототипы `novatip-ui/` или `design/`.
5. Не коммитить секреты, `.novalic`, дампы БД, `media/` с логотипами заказчика.

Опционально: GitHub Actions — lint (`ruff`), `manage.py check`, тесты на push.

---

## Порядок реализации (для агента)

1. Каркас Django + Docker Compose + `.env.example` + базовый chrome (сайдбар из прототипа).  
2. `accounts` + login (branding + cyber CSS) + роли.  
3. `core` Setup Wizard (включая **шаг БД: create user/grants/test**) + SystemSettings + branding.  
4. `licensing` клиент + минимальный `license_server` + `.novalic`.  
5. `vulns` модели, список с фильтрами, карточка (NVD↔BDU + блок CVSS), local ID.  
6. Sync NVD/KEV/BDU (Celery, checkpoint) + вкладка sync в settings.  
7. `tickets` + матрица переходов + модалки.  
8. `notify` SMTP + Telegram.  
9. `audit`, `/healthz`, hardening.  
10. **Документы 00–05 (с нуля для новичка)** + **создание GitHub repo и push**.

---

## Критерии приёмки

- [ ] Приложение поднимается через Docker Compose; открывается login → wizard (первый запуск) → dashboard.  
- [ ] UI на русском, без внешних CDN, стилистика как в `novatip-ui`.  
- [ ] Локальный префикс ID из мастера; создание `PREFIX-YYYY-NNNN`.  
- [ ] Карточка CVE: одна страница, NVD↔BDU, отдельный CVSS-блок с версиями.  
- [ ] Фильтры каталога сворачиваются; sync в настройках.  
- [ ] Заявки: исполнитель → resolved; закрытие только постановщиком/verifier.  
- [ ] **Мастер БД:** можно создать УЗ PostgreSQL + БД + GRANT и/или подключиться к существующей; «Проверить подключение» работает; `DATABASE_URL` сохраняется.  
- [ ] **docs/01…05** описывают путь от создания ВМ и установки ОС до первого входа — команды copy-paste, без допущений «вы уже знаете Linux».  
- [ ] Wiki отсутствует в меню, моделях и docs.  
- [ ] Код на GitHub; README ведёт на runbook; секретов в git нет.

---

## Явные запреты

- Не добавлять Wiki / knowledge-base модуль.  
- Не использовать CDN для JS/CSS/шрифтов.  
- Не дублировать CVE+BDU как две строки списка при связи по CVE.  
- Не хранить секреты в репозитории.  
- Не сохранять пароль PostgreSQL superuser после шага мастера.  
- Не делать саморегистрацию.  
- Не начинать «боевой» режим без wizard и лицензии (valid/grace).  
- Не переписывать UI в «современный SaaS purple» — держать enterprise console look.  
- Не писать docs в стиле «установите PostgreSQL сами» без команд — только пошагово.

---

**Начни с:** проверка workspace → `novatip-ui` как design reference → каркас Django + Compose → wizard с шагом БД (УЗ + права) → дальше по порядку → **полные docs 01–05 для новичка** → GitHub push и URL репозитория пользователю.
