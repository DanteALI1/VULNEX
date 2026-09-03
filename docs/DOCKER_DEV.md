# Docker Compose — локальная разработка VULNDB

## Запуск

```bash
cp .env.example .env
docker compose up --build
```

Откройте http://localhost:8000/

| Сервис | Порт | Назначение |
|---|---|---|
| web | 8000 | Django/Gunicorn |
| db | 5432 | PostgreSQL 16 |
| redis | 6379 | брокер Celery |
| worker | — | фоновые sync |
| beat | — | расписание |
| license_server | 8090 | выдача/heartbeat лицензий |

## Полезные команды

```bash
docker compose logs -f web
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py test
docker compose down -v   # удалить тома (данные БД)
```

В Compose роль/БД создаются init-скриптом. В мастере на шаге «База данных» достаточно подтвердить Compose-подключение.

## Без Docker

См. README: SQLite + `runserver` для быстрой проверки UI.  
