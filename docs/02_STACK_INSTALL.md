# 02. Установка стека на РЕД ОС 8

Все команды выполняйте от пользователя с `sudo` (например `deploy`).

## 1. Пакеты

```bash
sudo dnf -y install postgresql-server postgresql redis python3.12 python3.12-devel \
  gcc gcc-c++ make libpq-devel nginx firewalld git curl
```

Если имя пакета другое:

```bash
dnf search postgresql | head
dnf search python3.12 | head
```

## 2. PostgreSQL с нуля

```bash
sudo postgresql-setup --initdb || sudo /usr/bin/postgresql-setup --initdb
sudo systemctl enable --now postgresql
```

Создание УЗ и БД (режим «вручную»):

```bash
sudo -u postgres psql <<'SQL'
CREATE USER vulndb WITH PASSWORD 'CHANGE_ME_DB_PASSWORD';
CREATE DATABASE vulndb OWNER vulndb ENCODING 'UTF8';
GRANT ALL PRIVILEGES ON DATABASE vulndb TO vulndb;
\c vulndb
GRANT ALL ON SCHEMA public TO vulndb;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO vulndb;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO vulndb;
SQL
```

`pg_hba.conf` (localhost):

```bash
sudo sed -i 's/ident/scram-sha-256/g; s/peer/scram-sha-256/g' /var/lib/pgsql/data/pg_hba.conf
# путь к data может отличаться — найдите:
sudo find /var -name pg_hba.conf 2>/dev/null
sudo systemctl restart postgresql
```

Проверка:

```bash
psql "postgresql://vulndb:CHANGE_ME_DB_PASSWORD@127.0.0.1:5432/vulndb" -c 'SELECT 1;'
```

Ожидается строка `1`.

Альтернатива: создать УЗ через мастер VULNDB (режим B) — см. [04_WIZARD_AND_FIRST_LOGIN.md](04_WIZARD_AND_FIRST_LOGIN.md).

## 3. Redis

```bash
sudo systemctl enable --now redis
sudo redis-cli PING
```

Ожидается `PONG`. При необходимости задайте `requirepass` в `/etc/redis.conf` и перезапустите сервис.

## 4. Python 3.12+

```bash
python3.12 --version
```

Если команды нет — поставьте доступный `python3` ≥ 3.12 или модуль из репозитория РЕД ОС.

## 5. Nginx

```bash
sudo systemctl enable --now nginx
```

Конфиг приложения подключим на шаге [03_APP_INSTALL.md](03_APP_INSTALL.md).

## 6. firewalld

```bash
sudo systemctl enable --now firewalld
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
sudo firewall-cmd --list-services
```

## 7. SELinux

```bash
getenforce
# если Enforcing — позже зададим fcontext для static/media (шаг 03)
```

## Чеклист «готово, если…»

- [ ] `SELECT 1` к PostgreSQL под УЗ `vulndb` работает  
- [ ] `redis-cli PING` → PONG  
- [ ] Nginx и firewalld запущены  
- [ ] Дальше → [03_APP_INSTALL.md](03_APP_INSTALL.md)  
