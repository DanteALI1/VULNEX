#!/usr/bin/env bash
# VULNDB — быстрый локальный запуск через Docker Compose
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "Нужен Docker. Установите Docker Engine + Compose plugin." >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  # Generate local secrets
  if command -v openssl >/dev/null 2>&1; then
    SK="$(openssl rand -hex 32)"
    sed -i "s/^SECRET_KEY=.*/SECRET_KEY=${SK}/" .env || true
  fi
  sed -i 's|^DATABASE_URL=.*|DATABASE_URL=postgresql://vulndb:vulndb_dev_password@db:5432/vulndb|' .env || true
  echo "Создан .env из .env.example"
fi

export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-vulndb_dev_password}"

echo "==> docker compose up --build"
docker compose up --build -d

echo
echo "Готово:"
echo "  Web:             http://localhost:8000/"
echo "  License server:  http://localhost:8090/healthz"
echo "  Логи:            docker compose logs -f web"
echo "  Остановка:       docker compose down"
echo
echo "Первый запуск → мастер /setup/"
