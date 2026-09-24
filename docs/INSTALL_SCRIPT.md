# Скрипт установки VULNDB

## Production: `scripts/install-vulndb.sh`

Один скрипт для РЕД ОС 8 / RHEL-подобных систем (`dnf`/`yum`).

```bash
sudo bash scripts/install-vulndb.sh
```

**Текущий пароль УЗ `postgres` знать не нужно.** Скрипт входит в PostgreSQL через peer (`sudo -u postgres psql`) и сам задаёт новые пароли: роль приложения, по желанию суперпользователь `postgres`, веб-администратор. В конце печатает все данные и пишет копию в `/root/vulndb-install-credentials.txt`.

Не запускайте через `curl | sudo bash`, если хотите сами ввести пароли (нет TTY — всё сгенерируется). Скачайте репозиторий и запустите файл.

### Что ставит

1. Пакеты: PostgreSQL, Redis, Python 3, Nginx, firewalld, build-deps. Скрипт ищет unit `postgresql` / `postgresql-16` и вызывает `initdb`, если RPM создал пустой каталог данных.
2. `pg_hba`: `postgres` — peer (вход без пароля с ОС), остальные — пароль. Роль приложения и (опционально) `postgres` получают пароли, которые вы задали.
3. Redis (`PING`)
4. Пользователь ОС `vulndb`, каталоги `/opt/vulndb`, `/var/lib/vulndb`, `/var/log/vulndb`
5. Код (копия из текущего репо или `git clone`)
6. venv + `pip install -r requirements.txt`
7. `.env` с секретами
8. `migrate` + `collectstatic` + учётная запись веб-админа
9. systemd: `vulndb-web`, `vulndb-worker`, `vulndb-beat`
10. Nginx + firewalld http/https

### Переменные

| Переменная | Смысл |
|---|---|
| `VULNDB_DOMAIN` | Имя хоста для Nginx / ALLOWED_HOSTS |
| `VULNDB_DB_PASSWORD` | Пароль роли PostgreSQL приложения |
| `VULNDB_POSTGRES_PASSWORD` | Пароль суперпользователя `postgres` |
| `VULNDB_ADMIN_USER` | Логин веб-админа (по умолчанию `admin`) |
| `VULNDB_ADMIN_PASSWORD` | Пароль веб-админа |
| `VULNDB_ADMIN_NAME` | ФИО веб-админа |
| `VULNDB_REPO_URL` | Git URL, если кода ещё нет на диске |
| `VULNDB_SRC_DIR` | Путь к уже распакованному коду |
| `VULNDB_INSTALL_DIR` | Каталог установки (по умолчанию `/opt/vulndb`) |
| `VULNDB_SECRET_KEY` | Django SECRET_KEY |
| `VULNDB_ASSUME_YES=1` | Без вопросов, пароли генерируются |
| `VULNDB_SKIP_NGINX=1` | Не трогать Nginx |
| `VULNDB_SKIP_FIREWALL=1` | Не трогать firewalld |

Секреты: `/root/vulndb-install-credentials.txt` (режим 600).

После установки: браузер → `http://<host>/setup/`. Локальных пользователей с ролями создаёт администратор в разделе **Пользователи**.

## Dev: `scripts/install-docker-dev.sh`

```bash
bash scripts/install-docker-dev.sh
```

Поднимает Compose на http://localhost:8000/.
