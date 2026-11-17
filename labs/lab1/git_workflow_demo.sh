#!/usr/bin/env bash
# =============================================================================
# git_workflow_demo.sh
# Скрипт демонстрирует полный Git-процесс Лабораторной работы №1:
#   1. Первоначальный коммит проекта (main)
#   2. Работа через ветку feature/
#   3. Моделирование и разрешение конфликта слияния
#   4. Тег первой версии v0.1.0
#
# Запуск: bash git_workflow_demo.sh
# =============================================================================

set -e  # Остановить при ошибке

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
RESET='\033[0m'

step() { echo -e "\n${CYAN}══════════════════════════════════════════${RESET}"; \
         echo -e "${GREEN}▶ ШАГ: $1${RESET}"; \
         echo -e "${CYAN}══════════════════════════════════════════${RESET}"; }

# ─── НАСТРОЙКА ───────────────────────────────────────────────────────────────
step "Настройка git config"
git config user.email "student@cityduma.ru"
git config user.name "City Duma Student"

# ─── ШАГ 1: НАЧАЛЬНЫЙ КОММИТ ─────────────────────────────────────────────────
step "Первоначальный коммит проекта в main"

git add .gitignore .env.example README.md
git commit -m "chore: initial project setup

Add .gitignore, .env.example, README skeleton.
Topic: City Council (Городская Дума) management system."

git add requirements.txt pyproject.toml Makefile Dockerfile docker-compose.yml alembic.ini
git commit -m "chore: add project tooling

Add requirements.txt, pyproject.toml (ruff+pytest config),
Makefile with all standard targets, Dockerfile, docker-compose.yml,
alembic.ini for database migrations."

git add app/
git commit -m "feat: implement core application

Add FastAPI app with:
- SQLAlchemy async models (Deputy, Commission, CommissionMember, Session, Attendance)
- Pydantic v2 schemas with validators
- CRUD routers for all entities
- Jinja2 web interface (Bootstrap 5)
- /health endpoint
- Business rules:
  * Chair must be a commission member
  * Session quorum check (>50%) before marking as 'held'"

git add alembic/
git commit -m "feat(db): add Alembic migrations

Add alembic env.py (async), script template,
and initial migration 0001_initial.py creating all tables."

git add tests/
git commit -m "test: add API test suite

Add pytest-anyio tests covering:
- Health check
- Deputy CRUD + validation
- Commission chair business rule
- Session quorum business rule
- Attendance duplicate check"

git add docs/ CONTRIBUTING.md
git commit -m "docs: add project documentation

Add:
- docs/ТЗ.md — technical specification (GOST)
- docs/API.md — API reference
- docs/schema.md — data schema and ERD
- CONTRIBUTING.md — change management rules"

echo -e "${GREEN}✔ История main:${RESET}"
git log --oneline

# ─── ШАГ 2: FEATURE ВЕТКА ─────────────────────────────────────────────────────
step "Создание feature-ветки для новой функции (фильтрация депутатов)"

git checkout -b feature/deputy-active-filter

# Добавляем параметр фильтрации в роутер депутатов
cat >> app/routers/deputies.py << 'PATCH'


@router.get("/active", response_model=List[DeputyOut])
async def list_active_deputies(db: AsyncSession = Depends(get_db)):
    """Return only active deputies."""
    result = await db.execute(
        select(Deputy).where(Deputy.is_active == True).order_by(Deputy.id)  # noqa: E712
    )
    return result.scalars().all()
PATCH

git add app/routers/deputies.py
git commit -m "feat(deputies): add /active filter endpoint

Add GET /api/v1/deputies/active that returns
only deputies with is_active=True.

Closes #1"

# Добавляем тест для нового эндпоинта
cat >> tests/test_api.py << 'PATCH'


@pytest.mark.anyio
async def test_list_active_deputies(client):
    """Only active deputies should be returned from /active endpoint."""
    # Create active deputy
    await client.post("/api/v1/deputies/", json={"full_name": "Активный Депутат", "is_active": True})
    # Create inactive deputy
    await client.post("/api/v1/deputies/", json={"full_name": "Неактивный Депутат", "is_active": False})

    r = await client.get("/api/v1/deputies/active")
    assert r.status_code == 200
    names = [d["full_name"] for d in r.json()]
    assert "Активный Депутат" in names
    assert "Неактивный Депутат" not in names
PATCH

git add tests/test_api.py
git commit -m "test(deputies): add test for /active endpoint"

echo -e "${GREEN}✔ История feature/deputy-active-filter:${RESET}"
git log --oneline -5

# ─── ШАГ 3: КОНФЛИКТ СЛИЯНИЯ ─────────────────────────────────────────────────
step "Моделирование конфликта слияния"

# Параллельно изменяем README в main
git checkout main

# Изменяем строку в README (в main)
python -c "
content = open('README.md').read()
content = content.replace('[![Docker](', '[![Tests](https://img.shields.io/badge/tests-passing-green)]\n[![Docker](', 1)
open('README.md', 'w').write(content)
"
git add README.md
git commit -m "docs: add tests badge to README (main branch change)"

# Возвращаемся в feature-ветку и тоже меняем README
git checkout feature/deputy-active-filter

python -c "
content = open('README.md').read()
content = content.replace('[![Docker](', '[![Coverage](https://img.shields.io/badge/coverage-85%25-yellowgreen)]\n[![Docker](', 1)
open('README.md', 'w').write(content)
"
git add README.md
git commit -m "docs: add coverage badge to README (feature branch change)"

# Попытка слияния — будет конфликт
echo -e "${YELLOW}▶ Переключаемся в main для слияния...${RESET}"
git checkout main
echo -e "${YELLOW}▶ Выполняем merge — ожидается конфликт в README.md...${RESET}"
git merge feature/deputy-active-filter --no-ff || true

echo -e "${YELLOW}▶ Конфликт зафиксирован. Разрешаем вручную...${RESET}"

# Автоматически разрешаем конфликт: оставляем оба badge
python -c "
import re
content = open('README.md').read()
# Убираем маркеры конфликта, оставляем оба изменения
content = re.sub(r'<<<<<<< HEAD\n', '', content)
content = re.sub(r'=======\n', '', content)
content = re.sub(r'>>>>>>> feature/deputy-active-filter\n', '', content)
open('README.md', 'w').write(content)
print('Конфликт разрешён: оба badge сохранены')
"

git add README.md
git commit -m "merge: resolve conflict in README.md

Kept both badges:
- tests badge (from main)
- coverage badge (from feature/deputy-active-filter)

Merged feature/deputy-active-filter into main."

# ─── ШАГ 4: MERGE FEATURE ВЕТКИ ──────────────────────────────────────────────
step "Финальное состояние main после merge"
git log --oneline -10
git branch -d feature/deputy-active-filter

# ─── ШАГ 5: ТЕГ ВЕРСИИ ───────────────────────────────────────────────────────
step "Создание тега первой версии v0.1.0"

git tag -a v0.1.0 -m "Release v0.1.0 — Initial release

Features:
- Deputy management (CRUD)
- Commission management with membership
- Session management with quorum check
- Attendance tracking
- Web UI (Bootstrap 5 + Jinja2)
- REST API with OpenAPI docs
- /health endpoint
- Docker + docker-compose deployment
- Alembic migrations
- Pytest test suite
- Makefile with all standard targets"

echo ""
echo -e "${GREEN}══════════════════════════════════════════${RESET}"
echo -e "${GREEN}  ✔ Git-процесс завершён!${RESET}"
echo -e "${GREEN}══════════════════════════════════════════${RESET}"
echo ""
echo -e "${CYAN}Теги:${RESET}"
git tag -l
echo ""
echo -e "${CYAN}Полная история:${RESET}"
git log --oneline --graph --all
