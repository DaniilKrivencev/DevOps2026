# =============================================================================
# Городская Дума — Makefile
# Единый интерфейс для всех команд проекта
# =============================================================================

.PHONY: setup run test quality migrate backup restore verify up down \
        container-check help

PYTHON  := python
PIP     := pip
ALEMBIC := alembic
COMPOSE := docker compose

# Цвета
GREEN  := \033[0;32m
YELLOW := \033[0;33m
RED    := \033[0;31m
RESET  := \033[0m

# ─── Справка ─────────────────────────────────────────────────────────────────
help: ## Показать список команд
	@echo ""
	@echo "  Городская Дума — команды проекта"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ─── Первоначальная настройка ────────────────────────────────────────────────
setup: ## Первоначальная настройка (venv, зависимости, .env)
	@echo "$(GREEN)▶ Создание виртуального окружения...$(RESET)"
	$(PYTHON) -m venv .venv
	@echo "$(GREEN)▶ Установка зависимостей...$(RESET)"
	.venv/Scripts/pip install -r requirements.txt 2>/dev/null || \
	  .venv/bin/pip install -r requirements.txt
	@if [ ! -f .env ]; then \
	  cp .env.example .env; \
	  echo "$(YELLOW)⚠  Создан .env из .env.example — задайте свои значения!$(RESET)"; \
	fi
	@echo "$(GREEN)✔ Настройка завершена$(RESET)"

# ─── Локальный запуск ────────────────────────────────────────────────────────
run: ## Локальный запуск приложения (требует PostgreSQL)
	@echo "$(GREEN)▶ Запуск FastAPI на http://localhost:8000$(RESET)"
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# ─── Тесты ───────────────────────────────────────────────────────────────────
test: ## Запуск автоматических тестов
	@echo "$(GREEN)▶ Установка тестовых зависимостей...$(RESET)"
	$(PIP) install aiosqlite --quiet
	@echo "$(GREEN)▶ Запуск pytest...$(RESET)"
	pytest tests/ -v --tb=short
	@echo "$(GREEN)✔ Тесты завершены$(RESET)"

# ─── Качество кода ───────────────────────────────────────────────────────────
quality: ## Форматирование и статический анализ (ruff)
	@echo "$(GREEN)▶ Проверка форматирования (ruff)...$(RESET)"
	ruff check app/ tests/
	ruff format --check app/ tests/
	@echo "$(GREEN)✔ Качество кода OK$(RESET)"

quality-fix: ## Автоматически исправить ошибки форматирования
	ruff check --fix app/ tests/
	ruff format app/ tests/

# ─── Миграции ────────────────────────────────────────────────────────────────
migrate: ## Применить все миграции Alembic
	@echo "$(GREEN)▶ Применение миграций...$(RESET)"
	$(ALEMBIC) upgrade head
	@echo "$(GREEN)✔ Миграции применены$(RESET)"

migrate-down: ## Откатить последнюю миграцию
	$(ALEMBIC) downgrade -1

migrate-status: ## Показать состояние миграций
	$(ALEMBIC) current
	$(ALEMBIC) history --verbose

# ─── Резервное копирование ───────────────────────────────────────────────────
backup: ## Создать резервную копию БД
	@echo "$(GREEN)▶ Создание резервной копии...$(RESET)"
	@mkdir -p backups
	@BACKUP_FILE=backups/dump_$$(date +%Y%m%d_%H%M%S).sql; \
	  $(COMPOSE) exec -T db pg_dump \
	    -U $${POSTGRES_USER:-duma_user} \
	    $${POSTGRES_DB:-city_duma} > $$BACKUP_FILE; \
	  echo "$(GREEN)✔ Резервная копия: $$BACKUP_FILE$(RESET)"

restore: ## Восстановить резервную копию (BACKUP=backups/dump_xxx.sql)
	@if [ -z "$(BACKUP)" ]; then \
	  echo "$(RED)✗ Укажите файл: make restore BACKUP=backups/dump_xxx.sql$(RESET)"; exit 1; fi
	@echo "$(YELLOW)⚠  Восстановление из $(BACKUP)...$(RESET)"
	$(COMPOSE) exec -T db psql \
	  -U $${POSTGRES_USER:-duma_user} \
	  $${POSTGRES_DB:-city_duma} < $(BACKUP)
	@echo "$(GREEN)✔ Восстановление завершено$(RESET)"

# ─── Полная локальная проверка ────────────────────────────────────────────────
verify: ## Полный набор локальных проверок (quality + test)
	@echo "$(GREEN)═══════════════════════════════════════$(RESET)"
	@echo "$(GREEN)  Полная проверка проекта$(RESET)"
	@echo "$(GREEN)═══════════════════════════════════════$(RESET)"
	@$(MAKE) quality
	@$(MAKE) test
	@echo "$(GREEN)═══════════════════════════════════════$(RESET)"
	@echo "$(GREEN)  ✔ Все проверки пройдены$(RESET)"
	@echo "$(GREEN)═══════════════════════════════════════$(RESET)"

# ─── Docker ──────────────────────────────────────────────────────────────────
up: ## Запустить контейнерное окружение (build + up)
	@echo "$(GREEN)▶ Запуск контейнеров...$(RESET)"
	$(COMPOSE) up --build -d
	@echo "$(GREEN)✔ Приложение доступно на http://localhost:8000$(RESET)"

down: ## Остановить контейнерное окружение
	@echo "$(YELLOW)▶ Остановка контейнеров...$(RESET)"
	$(COMPOSE) down

down-volumes: ## Остановить контейнеры и УДАЛИТЬ данные
	@echo "$(RED)⚠  Удаление всех данных!$(RESET)"
	$(COMPOSE) down -v

logs: ## Показать логи приложения
	$(COMPOSE) logs -f app

# ─── Проверка контейнера ─────────────────────────────────────────────────────
container-check: ## Проверить работоспособность через health endpoint
	@echo "$(GREEN)▶ Проверка health endpoint...$(RESET)"
	@curl -sf http://localhost:8000/health | python -m json.tool || \
	  (echo "$(RED)✗ Приложение недоступно$(RESET)" && exit 1)
	@echo "$(GREEN)✔ Приложение работает$(RESET)"
