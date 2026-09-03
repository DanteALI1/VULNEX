# 03. Установка приложения VULNDB

## 1. Пользователь и каталоги

```bash
sudo useradd --system --home /opt/vulndb --shell /sbin/nologin vulndb || true
sudo mkdir -p /opt/vulndb /var/lib/vulndb/media /var/log/vulndb
sudo chown -R vulndb:vulndb /opt/vulndb /var/lib/vulndb /var/log/vulndb
```

## 2. Получение кода

```bash
sudo dnf -y install git
cd /opt
sudo -u vulndb git clone CHANGE_ME_REPO_URL vulndb
# или распакуйте release-архив в /opt/vulndb
```

## 3. venv и зависимости

```bash
cd /opt/vulndb
sudo -u vulndb python3.12 -m venv .venv
sudo -u vulndb .venv/bin/pip install -U pip
sudo -u vulndb .venv/bin/pip install -r requirements.txt
```

## 4. Файл `.env`

```bash
sudo -u vulndb cp .env.example .env
sudo -u vulndb chmod 600 .env
sudo -u vulndb nano .env
```

Пояснения полей:

| Переменная | Простыми словами |
|---|---|
| `SECRET_KEY` | Секрет подписей сессий. Сгенерируйте длинную случайную строку. |
| `DEBUG` | В проде `0`. |
| `ALLOWED_HOSTS` | Имя/IP сайта, например `vulndb.example.ru`. |
| `DATABASE_URL` | Строка подключения PostgreSQL. |
| `REDIS_URL` | Адрес Redis. |
| `LICENSE_SERVER_URL` | URL сервера лицензий вендора. |
| `LICENSE_FILE` | Путь к файлу `.novalic`. |

Пример `DATABASE_URL`:

```text
postgresql://vulndb:CHANGE_ME_DB_PASSWORD@127.0.0.1:5432/vulndb
```

## 5. Миграции и статика

```bash
cd /opt/vulndb
sudo -u vulndb .venv/bin/python manage.py migrate --noinput
sudo -u vulndb .venv/bin/python manage.py collectstatic --noinput
```

## 6. systemd

```bash
sudo cp deploy/systemd/vulndb-web.service /etc/systemd/system/
sudo cp deploy/systemd/vulndb-worker.service /etc/systemd/system/
sudo cp deploy/systemd/vulndb-beat.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now vulndb-web vulndb-worker vulndb-beat
sudo systemctl status vulndb-web --no-pager
```

## 7. Nginx + TLS

```bash
sudo cp deploy/nginx/vulndb.conf /etc/nginx/conf.d/vulndb.conf
sudo sed -i 's/CHANGE_ME_HOSTNAME/vulndb.example.ru/' /etc/nginx/conf.d/vulndb.conf
sudo nginx -t
sudo systemctl reload nginx
```

Лабораторный self-signed:

```bash
sudo mkdir -p /etc/ssl/vulndb
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/vulndb/privkey.pem \
  -out /etc/ssl/vulndb/fullchain.pem \
  -subj "/CN=vulndb.example.ru"
```

Для Let's Encrypt используйте `certbot` по политике площадки.

SELinux (если Enforcing):

```bash
sudo semanage fcontext -a -t httpd_sys_content_t '/opt/vulndb/staticfiles(/.*)?'
sudo semanage fcontext -a -t httpd_sys_rw_content_t '/var/lib/vulndb/media(/.*)?'
sudo restorecon -Rv /opt/vulndb/staticfiles /var/lib/vulndb/media
sudo setsebool -P httpd_can_network_connect 1
```

## 8. Проверка

```bash
curl -k https://127.0.0.1/healthz
# или
curl http://127.0.0.1/healthz
```

Ожидается: `ok`.

## Чеклист «готово, если…»

- [ ] Три unit'а active  
- [ ] `/healthz` отвечает `ok`  
- [ ] Дальше → [04_WIZARD_AND_FIRST_LOGIN.md](04_WIZARD_AND_FIRST_LOGIN.md)  
