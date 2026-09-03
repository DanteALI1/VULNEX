#!/usr/bin/env bash
# Обёртка: канонический установщик — scripts/install-vulndb.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec bash "$ROOT/scripts/install-vulndb.sh" "$@"
