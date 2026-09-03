# 00. Обзор VULNDB

VULNDB — локальная база уязвимостей для площадки заказчика.

```text
[Браузер]
    |
    v
[Nginx :443] ---- static/media
    |
    v
[Gunicorn web :8000] ---- Django apps (accounts/core/vulns/tickets/…)
    |                 \
    |                  +--> [License Server] (heartbeat)
    v
[PostgreSQL 16]     [Redis 7] <--- [Celery worker] + [Celery beat]
```

## Что куда ставится

| Компонент | Где |
|---|---|
| Код приложения | `/opt/vulndb` |
| Медиа (логотипы) | `/var/lib/vulndb/media` |
| Логи | `/var/log/vulndb` |
| PostgreSQL | системный пакет / сервис `postgresql` |
| Redis | системный пакет / сервис `redis` |
| Reverse proxy | Nginx |

## Чеклист «готово, если…»

- [ ] Понимаете, что VULNDB — веб-приложение + БД + очередь фоновых задач  
- [ ] Есть ВМ (или физический сервер) под РЕД ОС 8  
- [ ] Переходите к [01_VM_AND_OS.md](01_VM_AND_OS.md)  
