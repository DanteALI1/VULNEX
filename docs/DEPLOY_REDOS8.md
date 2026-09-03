# Сводный чеклист деплоя РЕД ОС 8

1. [ ] ВМ создана, ISO РЕД ОС 8 установлен — [01](01_VM_AND_OS.md)  
2. [ ] Сеть/SSH/`dnf update` — [01](01_VM_AND_OS.md)  
3. [ ] PostgreSQL УЗ+БД, Redis, Python, Nginx, firewall — [02](02_STACK_INSTALL.md)  
4. [ ] Код в `/opt/vulndb`, venv, `.env`, migrate, systemd — [03](03_APP_INSTALL.md)  
5. [ ] Nginx + TLS, `/healthz` = ok — [03](03_APP_INSTALL.md)  
6. [ ] Мастер `/setup/` (лицензия → орг → БД → админ → …) — [04](04_WIZARD_AND_FIRST_LOGIN.md)  
7. [ ] Первый вход, sync в Настройках — [04](04_WIZARD_AND_FIRST_LOGIN.md)  
8. [ ] Бэкап настроен — [05](05_OPERATIONS.md)  

Архитектура: [00_OVERVIEW.md](00_OVERVIEW.md).  
Docker для разработки: [DOCKER_DEV.md](DOCKER_DEV.md).  
