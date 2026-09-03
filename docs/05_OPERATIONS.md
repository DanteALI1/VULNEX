# 05. Эксплуатация

## Бэкап

PostgreSQL:

```bash
sudo -u postgres pg_dump -Fc vulndb > /var/backups/vulndb-$(date +%F).dump
```

Медиа и `.env`:

```bash
sudo tar czf /var/backups/vulndb-media-$(date +%F).tgz -C /var/lib/vulndb media
sudo cp /opt/vulndb/.env /var/backups/vulndb.env-$(date +%F)
```

## Обновление

```bash
cd /opt/vulndb
sudo -u vulndb git pull
sudo -u vulndb .venv/bin/pip install -r requirements.txt
sudo -u vulndb .venv/bin/python manage.py migrate --noinput
sudo -u vulndb .venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart vulndb-web vulndb-worker vulndb-beat
```

## Логи

```bash
sudo journalctl -u vulndb-web -f
sudo journalctl -u vulndb-worker -f
sudo tail -f /var/log/nginx/error.log
```

## Типичные ошибки

| Симптом | Что проверить |
|---|---|
| 502 Bad Gateway | `systemctl status vulndb-web`, порт 8000 |
| Ошибка БД на login | `DATABASE_URL`, `pg_hba.conf`, пароль УЗ |
| Sync NVD error | API key / сеть до `services.nvd.nist.gov` |
| Лицензия blocked | `.novalic`, fingerprint, grace 14 дней |
| Статика 404 | `collectstatic`, alias Nginx, SELinux fcontext |

## Чеклист «готово, если…»

- [ ] Есть свежий dump БД  
- [ ] Знаете, как смотреть journalctl  
- [ ] Знаете путь отката (предыдущий release + restore dump)  
