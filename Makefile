# =============================================================================
# Городская Дума — единый интерфейс команд проекта
#   make verify           — весь обязательный набор локальных проверок (ЛР3)
#   make container-check  — проверка контейнерного окружения (ЛР4)
# =============================================================================

.PHONY: help setup install run lint format sast policy test test-unit test-integration test-pg \
        mutation audit lock docker-build docker-up docker-down docker-ps docker-logs docker-migrate \
        docker-backup docker-restore docker-restore-new-volume container-lint container-check ci \
        cd-deploy cd-rollback cd-status cd-verify cd-demo-images \
        migrate migrate-down migrate-status migrate-new migrate-check migrate-check-pg \
        seed backup restore restore-demo verify clean

VENV    := .venv
PY      := $(shell [ -x $(VENV)/bin/python ] && echo $(VENV)/bin/python || echo python3)
REPORTS := reports
SRC     := app scripts tests alembic

# Версия и тег образа: версия приложения + короткий SHA коммита (не latest)
GIT_SHA     := $(shell git rev-parse --short=12 HEAD 2>/dev/null || echo nogit)
APP_VERSION := $(shell sed -n 's/^APP_VERSION = "\(.*\)"/\1/p' app/main.py)
APP_TAG     ?= $(APP_VERSION)-$(GIT_SHA)
export GIT_SHA APP_VERSION APP_TAG
COMPOSE     := docker compose
BACKUP_DIR  := backups

# Пороги. Снижать запрещено — проверяет scripts/check_policy.py
MUTATION_MIN := 90

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
	$(PY) -m pip install -r requirements-dev.txt -c requirements.lock

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

sast: ## Статический анализ безопасности (bandit), отчёт в reports/
	@echo "$(GREEN)▶ bandit (SAST)$(RESET)"
	@mkdir -p $(REPORTS)
	$(PY) -m bandit -c pyproject.toml -r app scripts -f json -o $(REPORTS)/bandit.json -q || true
	$(PY) -m bandit -c pyproject.toml -r app scripts

audit: ## Уязвимости рабочих зависимостей (pip-audit по requirements.lock), отчёт reports/pip-audit.json
	@echo "$(GREEN)▶ pip-audit$(RESET)"
	@mkdir -p $(REPORTS)
	-$(PY) -m pip_audit -r requirements.lock --no-deps --disable-pip -f json -o $(REPORTS)/pip-audit.json
	$(PY) -m pip_audit -r requirements.lock --no-deps --disable-pip

lock: ## Пересобрать requirements.lock из requirements.txt в чистом venv
	rm -rf .lockvenv && $(PY) -m venv .lockvenv
	.lockvenv/bin/pip install -q -r requirements.txt
	{ head -n 2 requirements.lock; .lockvenv/bin/pip freeze; } > requirements.lock.new
	mv requirements.lock.new requirements.lock && rm -rf .lockvenv

policy: ## Запрет пропуска тестов, снижения порогов и исключений без обоснования
	@echo "$(GREEN)▶ Проверка правил проекта$(RESET)"
	$(PY) scripts/check_policy.py

# ─── Тесты ───────────────────────────────────────────────────────────────────
test: ## Все тесты + отчёты (JUnit, покрытие HTML/XML) с порогом покрытия
	@echo "$(GREEN)▶ pytest (unit + integration)$(RESET)"
	@mkdir -p $(REPORTS)
	$(PY) -m pytest --cov --cov-report=term --cov-report=html:$(REPORTS)/htmlcov \
	  --cov-report=xml:$(REPORTS)/coverage.xml --junitxml=$(REPORTS)/junit.xml

test-unit: ## Только unit-тесты
	$(PY) -m pytest -m unit

test-integration: ## Только интеграционные тесты (БД, миграции, бэкапы)
	$(PY) -m pytest -m integration

test-pg: ## Тесты на PostgreSQL (нужен TEST_DATABASE_URL=postgresql+asyncpg://...)
	@if [ -z "$$TEST_DATABASE_URL" ]; then echo "$(RED)✗ задайте TEST_DATABASE_URL$(RESET)"; exit 1; fi
	$(PY) -m pytest

mutation: ## Мутационное тестирование бизнес-правил (mutmut), порог MUTATION_MIN
	@echo "$(GREEN)▶ mutmut: app/services.py$(RESET)"
	@mkdir -p $(REPORTS) && rm -f .mutmut-cache
	-$(PY) -m mutmut run --paths-to-mutate app/services.py --tests-dir tests/unit \
	  --runner "$(PY) -m pytest -x -q -p no:cacheprovider tests/unit" > $(REPORTS)/mutmut.log 2>&1
	$(PY) scripts/check_mutation.py $(MUTATION_MIN)

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

migrate-check: ## Чистая БД с нуля + проверка, что модели совпадают с миграциями
	@echo "$(GREEN)▶ Миграции на чистой БД + alembic check$(RESET)"
	@mkdir -p $(REPORTS) && rm -f $(REPORTS)/migrate_check.db
	APP_ENV=development DATABASE_URL=sqlite+aiosqlite:///./$(REPORTS)/migrate_check.db \
	  sh -c '$(PY) -m alembic upgrade head && $(PY) -m alembic check'

migrate-check-pg: ## Миграции на PostgreSQL: чистая БД → данные → откат → повторное применение (PG_URL=...)
	@if [ -z "$$PG_URL" ]; then echo "$(RED)✗ задайте PG_URL=postgresql+asyncpg://...$(RESET)"; exit 1; fi
	@echo "$(GREEN)▶ Миграции на чистой БД PostgreSQL$(RESET)"
	APP_ENV=development DATABASE_URL=$$PG_URL $(PY) -m alembic downgrade base
	APP_ENV=development DATABASE_URL=$$PG_URL $(PY) -m alembic upgrade head
	APP_ENV=development DATABASE_URL=$$PG_URL $(PY) -m alembic check
	@echo "$(GREEN)▶ Обновление БД с данными: seed → откат до 0002 → upgrade head$(RESET)"
	APP_ENV=development DATABASE_URL=$$PG_URL $(PY) -m scripts.seed
	APP_ENV=development DATABASE_URL=$$PG_URL $(PY) -m alembic downgrade 0002
	APP_ENV=development DATABASE_URL=$$PG_URL $(PY) -m alembic upgrade head
	APP_ENV=development DATABASE_URL=$$PG_URL $(PY) -m alembic current

seed: ## Наполнить БД демонстрационными данными
	$(PY) -m scripts.seed

# ─── Резервное копирование ───────────────────────────────────────────────────
backup: ## Резервная копия БД в backups/ (pg_dump или копия SQLite)
	$(PY) -m scripts.db_backup backup

restore: ## Восстановление: make restore BACKUP=backups/dump_xxx.sql
	@if [ -z "$(BACKUP)" ]; then \
	  echo "$(RED)✗ Укажите файл: make restore BACKUP=backups/dump_xxx.sql$(RESET)"; exit 1; fi
	$(PY) -m scripts.db_backup restore $(BACKUP)

restore-demo: ## Демонстрация: бэкап → удаление/порча данных → восстановление
	PY=$(PY) ./scripts/restore_demo.sh

# ─── Единая проверка ─────────────────────────────────────────────────────────
verify: ## ВЕСЬ обязательный набор проверок: policy, lint, sast, migrate-check, test, mutation
	@echo "$(GREEN)══════ make verify ══════$(RESET)"
	@$(MAKE) --no-print-directory policy
	@$(MAKE) --no-print-directory lint
	@$(MAKE) --no-print-directory sast
	@$(MAKE) --no-print-directory migrate-check
	@$(MAKE) --no-print-directory test
	@$(MAKE) --no-print-directory mutation
	@echo "$(GREEN)  отчёты: $(REPORTS)/junit.xml, $(REPORTS)/htmlcov/index.html$(RESET)"
	@echo "$(GREEN)══════ ✔ Все проверки пройдены ══════$(RESET)"

clean: ## Удалить отчёты и кэши
	rm -rf $(REPORTS) .pytest_cache .ruff_cache .coverage .mutmut-cache

# ─── Контейнеры (ЛР4) ────────────────────────────────────────────────────────
docker-build: ## Собрать образ приложения cityduma:$(APP_TAG)
	$(COMPOSE) build app1

docker-up: ## Поднять окружение: db, migrate, app1, app2, nginx (http://localhost:8080)
	$(COMPOSE) up -d --build --wait
	$(COMPOSE) ps

docker-down: ## Остановить окружение (данные в volume сохраняются)
	$(COMPOSE) down

docker-ps: ## Состояние контейнеров и healthcheck
	$(COMPOSE) ps

docker-logs: ## Журналы всех контейнеров
	$(COMPOSE) logs -f --tail=100

docker-migrate: ## Применить миграции в контейнерной среде
	$(COMPOSE) run --rm migrate alembic upgrade head
	$(COMPOSE) run --rm migrate alembic current

docker-backup: ## Резервная копия БД из контейнера → backups/pg_<время>.dump
	@mkdir -p $(BACKUP_DIR)
	@f=$(BACKUP_DIR)/pg_$$(date +%Y%m%d_%H%M%S).dump; \
	  $(COMPOSE) exec -T db sh -c 'pg_dump -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -Fc' > $$f \
	  && echo "✔ резервная копия: $$f ($$(du -h $$f | cut -f1))"

docker-restore: ## Восстановить БД в контейнере: make docker-restore BACKUP=backups/pg_xxx.dump
	@if [ -z "$(BACKUP)" ]; then echo "$(RED)✗ make docker-restore BACKUP=backups/<файл>.dump$(RESET)"; exit 1; fi
	$(COMPOSE) exec -T db sh -c 'pg_restore -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" --clean --if-exists' < $(BACKUP)
	@echo "✔ восстановлено из $(BACKUP)"

docker-restore-new-volume: ## Восстановить в НОВЫЙ volume: make docker-restore-new-volume BACKUP=... VOLUME=имя
	@if [ -z "$(BACKUP)" ] || [ -z "$(VOLUME)" ]; then \
	  echo "$(RED)✗ make docker-restore-new-volume BACKUP=backups/<файл>.dump VOLUME=<новый volume>$(RESET)"; exit 1; fi
	$(COMPOSE) down
	PG_VOLUME=$(VOLUME) $(COMPOSE) up -d --wait db
	PG_VOLUME=$(VOLUME) $(COMPOSE) exec -T db sh -c 'pg_restore -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" --no-owner' < $(BACKUP)
	PG_VOLUME=$(VOLUME) $(COMPOSE) up -d --wait
	@echo "✔ окружение работает на volume $(VOLUME); для постоянного использования задайте PG_VOLUME=$(VOLUME) в .env"

container-lint: ## Запреты: latest, root, секреты в образе, отключённый healthcheck, лишние порты
	PY=$(PY) ./scripts/container_check.sh lint

container-check: ## ПОЛНАЯ проверка контейнерного окружения на отдельном стенде (обязательна перед изменением)
	PY=$(PY) ./scripts/container_check.sh

# ─── CI (ЛР5): те же этапы, что в GitHub Actions, локально в контейнерах ─────
ci: ## Весь pipeline локально: style, test, migrations, backup, security, build, container
	./scripts/ci.sh all

ci-%: ## Один этап CI: make ci-style | ci-test | ci-migrations | ci-backup | ci-security | ci-build | ci-container
	./scripts/ci.sh $*

# ─── CD (ЛР6): тестовое окружение staging ────────────────────────────────────
# Нужны STAGING_HOST и STAGING_SSH_KEY (ключ учётной записи cd-deploy) или DEPLOY_TARGET=local.
cd-deploy: ## Выпустить тег на staging: make cd-deploy TAG=sha-<commit>|X.Y.Z
	@if [ -z "$(TAG)" ]; then echo "$(RED)✗ make cd-deploy TAG=sha-<commit>$(RESET)"; exit 1; fi
	./scripts/cd.sh deploy $(TAG)

cd-rollback: ## Ручной возврат: make cd-rollback [TAG=<тег>] (по умолчанию — предыдущая успешная версия)
	./scripts/cd.sh rollback $(TAG)

cd-status: ## Версия, история выпусков и контейнеры на staging
	./scripts/cd.sh status

cd-verify: ## Проверить работающий релиз (контейнеры, /health, /version, основной сценарий)
	./scripts/cd.sh verify

cd-demo-images: ## Образы «неудачных выпусков» для защиты: make cd-demo-images BASE=<образ:тег>
	@if [ -z "$(BASE)" ]; then echo "$(RED)✗ make cd-demo-images BASE=ghcr.io/...:sha-...$(RESET)"; exit 1; fi
	docker build -f deploy/staging/demo/Dockerfile --target broken-health \
	  --build-arg BASE=$(BASE) --build-arg DEMO_COMMIT=de0000000001 -t $(firstword $(subst :, ,$(BASE))):sha-de0000000001 .
	docker build -f deploy/staging/demo/Dockerfile --target broken-scenario \
	  --build-arg BASE=$(BASE) --build-arg DEMO_COMMIT=de0000000002 -t $(firstword $(subst :, ,$(BASE))):sha-de0000000002 .
	@echo "✔ sha-de0000000001 (healthcheck), sha-de0000000002 (основной сценарий); опубликуйте: docker push <образ>:<тег>"
