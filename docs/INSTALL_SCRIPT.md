# Скрипт установки VULNDB

## Production: `scripts/install-vulndb.sh`

Один скрипт для РЕД ОС 8 / RHEL-подобных систем (`dnf`/`yum`).

```bash
sudo bash scripts/install-vulndb.sh
```

### Что ставит

1. Пакеты: PostgreSQL, Redis, Python 3, Nginx, firewalld, build-deps  
2. БД и роль `vulndb` + проверка `SELECT 1`  
3. Redis (`PING`)  
4. Пользователь ОС `vulndb`, каталоги `/opt/vulndb`, `/var/lib/vulndb`, `/var/log/vulndb`  
5. Код (копия из текущего репо или `git clone`)  
6. venv + `pip install -r requirements.txt`  
7. `.env` с секретами  
8. `migrate` + `collectstatic`  
9. systemd: `vulndb-web`, `vulndb-worker`, `vulndb-beat`  
10. Nginx + firewalld http/https  

### Переменные

| Переменная | Смысл |
|---|---|
| `VULNDB_DOMAIN` | Имя хоста для Nginx / ALLOWED_HOSTS |
| `VULNDB_REPO_URL` | Git URL, если кода ещё нет на диске |
| `VULNDB_SRC_DIR` | Путь к уже распакованному коду |
| `VULNDB_INSTALL_DIR` | Каталог установки (по умолчанию `/opt/vulndb`) |
| `VULNDB_DB_PASSWORD` | Пароль УЗ PostgreSQL (иначе генерируется) |
| `VULNDB_SECRET_KEY` | Django SECRET_KEY |
| `VULNDB_ASSUME_YES=1` | Без вопросов |
| `VULNDB_SKIP_NGINX=1` | Не трогать Nginx |
| `VULNDB_SKIP_FIREWALL=1` | Не трогать firewalld |

Секреты: `/root/vulndb-install-credentials.txt`.

После установки: браузер → `http://<host>/setup/`.

## Dev: `scripts/install-docker-dev.sh`

```bash
bash scripts/install-docker-dev.sh
```

Поднимает Compose на http://localhost:8000/.
