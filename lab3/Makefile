# =============================================================================
# Городская Дума — Лабораторная работа №3
# Единый локальный проверочный контур: make verify
# =============================================================================

.PHONY: help setup install run lint format test migrate migrate-down migrate-status \
        migrate-new backup restore verify clean

VENV    := .venv
PY      := $(shell [ -x $(VENV)/bin/python ] && echo $(VENV)/bin/python || echo python3)
REPORTS := reports
SRC     := app scripts tests alembic

GREEN  := \033[0;32m
YELLOW := \033[0;33m
RED    := \033[0;31m
RESET  := \033[0m

help: ## Показать список команд
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ─── Установка и запуск ──────────────────────────────────────────────────────
setup: ## Первоначальная настройка проекта (единый сценарий setup.sh)
	./setup.sh

install: ## Установить зафиксированные зависимости в .venv
	$(PY) -m pip install -r requirements-dev.txt

run: ## Запустить приложение на http://localhost:8000
	$(PY) -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# ─── Качество кода ───────────────────────────────────────────────────────────
lint: ## Линтер и проверка форматирования (ruff)
	@echo "$(GREEN)▶ ruff check + ruff format --check$(RESET)"
	$(PY) -m ruff check $(SRC)
	$(PY) -m ruff format --check $(SRC)

format: ## Автоисправление форматирования
	$(PY) -m ruff check --fix $(SRC)
	$(PY) -m ruff format $(SRC)

# ─── Тесты ───────────────────────────────────────────────────────────────────
test: ## Запуск тестов
	@echo "$(GREEN)▶ pytest$(RESET)"
	$(PY) -m pytest

# ─── Миграции ────────────────────────────────────────────────────────────────
migrate: ## Применить все миграции (alembic upgrade head)
	$(PY) -m alembic upgrade head

migrate-down: ## Откатить последнюю миграцию
	$(PY) -m alembic downgrade -1

migrate-status: ## Текущая ревизия и история миграций
	$(PY) -m alembic current
	$(PY) -m alembic history

migrate-new: ## Создать миграцию: make migrate-new MSG="описание"
	$(PY) -m alembic revision --autogenerate -m "$(MSG)"

# ─── Резервное копирование ───────────────────────────────────────────────────
backup: ## Резервная копия БД в backups/ (pg_dump или копия SQLite)
	$(PY) -m scripts.db_backup backup

restore: ## Восстановление: make restore BACKUP=backups/dump_xxx.sql
	@if [ -z "$(BACKUP)" ]; then \
	  echo "$(RED)✗ Укажите файл: make restore BACKUP=backups/dump_xxx.sql$(RESET)"; exit 1; fi
	$(PY) -m scripts.db_backup restore $(BACKUP)

# ─── Единая проверка ─────────────────────────────────────────────────────────
verify: ## Обязательный набор проверок
	@echo "$(GREEN)══════ make verify ══════$(RESET)"
	@$(MAKE) --no-print-directory lint
	@$(MAKE) --no-print-directory test
	@echo "$(GREEN)══════ ✔ Все проверки пройдены ══════$(RESET)"

clean: ## Удалить отчёты и кэши
	rm -rf $(REPORTS) .pytest_cache .ruff_cache .coverage
