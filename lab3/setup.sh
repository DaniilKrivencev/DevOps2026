#!/usr/bin/env bash
# =============================================================================
# Единый сценарий первоначальной настройки проекта (ЛР3).
#   ./setup.sh            — venv, зависимости, .env, миграции, проверка
#   SKIP_VERIFY=1 ./setup.sh — без финального make verify
# Повторный запуск безопасен (идемпотентен).
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"

PYTHON=${PYTHON:-python3}

echo "▶ 1/5 Проверка версии Python (нужна 3.12+)"
$PYTHON - <<'PYEOF'
import sys
if sys.version_info < (3, 12):
    sys.exit(f"✗ Нужен Python 3.12+, найден {sys.version.split()[0]}")
print(f"  Python {sys.version.split()[0]} — OK")
PYEOF

echo "▶ 2/5 Виртуальное окружение .venv"
[ -d .venv ] || $PYTHON -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip

echo "▶ 3/5 Установка зафиксированных зависимостей"
.venv/bin/python -m pip install --quiet -r requirements-dev.txt

echo "▶ 4/5 Конфигурация .env"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "  создан .env из .env.example (по умолчанию SQLite, для PostgreSQL задайте DATABASE_URL)"
else
  echo "  .env уже существует — не изменяю"
fi

echo "▶ 5/5 Миграции БД"
.venv/bin/python -m alembic upgrade head

if [ "${SKIP_VERIFY:-0}" != "1" ]; then
  echo "▶ Финальная проверка: make verify"
  make verify
fi

echo "✔ Проект готов. Запуск: make run → http://localhost:8000"
