# Городская Дума — City Council Management System

[![CI](https://github.com/DaniilKrivencev/DevOps2026/actions/workflows/ci.yml/badge.svg)](https://github.com/DaniilKrivencev/DevOps2026/actions/workflows/ci.yml)

> Система учёта депутатов, комиссий, заседаний, повестки и посещаемости городской думы.
> Сквозной проект курса DevOps: все лабораторные работы ведутся в одном репозитории.

**Стек:** Python 3.12 · FastAPI · SQLAlchemy (async) · Alembic · PostgreSQL 16 · Jinja2 (веб-интерфейс)

---

## Назначение системы

Веб-приложение (HTTP API + веб-интерфейс) для учёта:
- **Депутатов** (ФИО, партия, округ, дата избрания, статус, контакты)
- **Комиссий** (название, описание, председатель, состав)
- **Заседаний** (дата, тема, статус, привязка к комиссии) и **повестки** заседания
- **Посещаемости** (явка депутатов на заседания)

Техническое задание — [labs/lab1/ТЗ.md](labs/lab1/ТЗ.md), API — [labs/lab1/API.md](labs/lab1/API.md),
схема данных — [labs/lab1/schema.md](labs/lab1/schema.md).

## Пользователи и роли

| Роль | Права |
|------|-------|
| `admin` | все операции (депутаты, комиссии, удаление) |
| `secretary` | ведение заседаний, повестки и посещаемости |
| без входа | просмотр данных (GET) |

Изменяющие запросы требуют HTTP Basic-авторизации (см. «Авторизация» ниже).

## Правила предметной области

1. **Председатель комиссии** обязан быть её членом (иначе HTTP 422).
2. **Кворум**: заседание можно пометить «Проведено», только если присутствовало более 50% членов комиссии.
3. **Удаление председателя** из членов комиссии запрещено без смены председателя.
4. Одна запись посещаемости на пару «депутат + заседание» (уникальность на уровне БД).

---

## Быстрый старт

**Docker (рекомендуется):**

```bash
cp .env.example .env    # задать POSTGRES_PASSWORD и APP_AUTH_USERS
make docker-up          # db, migrate, app1, app2, nginx → http://localhost:8080
make container-check    # проверка контейнерного окружения
```

**Локально без Docker:**

```bash
./setup.sh          # Linux/macOS/Git Bash: venv, зависимости, .env, миграции, make verify
make run            # http://localhost:8000  (Swagger: /docs, health: /health)
```

Windows (PowerShell): `py -3.12 -m venv .venv; .venv\Scripts\pip install -r requirements-dev.txt -c requirements.lock; Copy-Item .env.example .env; .venv\Scripts\uvicorn app.main:app --reload`

## Команды

`make help` — полный список. Основные:

| Назначение | Команда |
|---|---|
| установка / первичная настройка | `make setup`, `make install` |
| запуск | `make run` |
| проверка (всё) | **`make verify`** = `policy` → `lint` → `sast` → `migrate-check` → `test` → `mutation` |
| миграции | `make migrate`, `make migrate-down`, `make migrate-status`, `make migrate-check` |
| резервная копия / восстановление | `make backup`, `make restore BACKUP=backups/<файл>`, `make restore-demo` |
| контейнеры | `make docker-up`, `make docker-down`, `make docker-backup`, `make docker-restore BACKUP=...` |
| проверка контейнерного окружения | **`make container-check`** (запреты + 12 проверок на отдельном стенде) |
| pipeline CI локально (в контейнерах) | `make ci`, `make ci-<этап>`; уязвимости зависимостей — `make audit` |

## Структура

```
.
├── app/                 # FastAPI-приложение (роутеры, модели, схемы, бизнес-правила)
├── alembic/versions/    # миграции 0001 … 0004
├── tests/unit/          # unit-тесты
├── tests/integration/   # интеграционные тесты (БД, миграции, бэкапы, API)
├── scripts/             # backup/restore, политика проверок, seed
├── deploy/              # ЛР2: развёртывание на двух Linux-ВМ без контейнеров
├── Vagrantfile          # ЛР2: ВМ app + db; ЛР4: ВМ docker
├── Dockerfile, .dockerignore, docker-compose.yml, nginx/   # ЛР4
├── .github/             # ЛР5: workflows CI, CODEOWNERS
├── labs/lab1 … lab6/    # отчёты и материалы по каждой лабораторной (см. labs/README.md)
├── Makefile             # единый интерфейс команд
└── CONTRIBUTING.md      # правила внесения изменений (GitFlow, запреты, приёмка)
```

## Лабораторные работы

Каждая лабораторная — в своём каталоге [`labs/`](labs/README.md): отчёт (`README.md`),
список файлов проекта, которые к ней относятся, и команды для проверки на защите.
Само приложение одно и лежит в корне — так требует задание (один репозиторий,
сквозной проект), и только так работают `make`, Docker, CI и CD.

| ЛР | Тема | Каталог | Тег |
|----|------|---------|-----|
| 1 | Сквозной проект и Git-процесс | [labs/lab1](labs/lab1/README.md) | `v0.1.0` |
| 2 | Развёртывание в Linux-среде | [labs/lab2](labs/lab2/README.md) | — |
| 3 | Автоматические проверки, миграции, бэкапы | [labs/lab3](labs/lab3/README.md) | — |
| 4 | Контейнеризация и проверка окружения | [labs/lab4](labs/lab4/README.md) | `v0.5.0` |
| 5 | Continuous Integration | [labs/lab5](labs/lab5/README.md) | `v0.5.0` |
| 6 | Continuous Delivery и проверка релиза | [labs/lab6](labs/lab6/README.md) | `v0.6.0` |

## Конфигурация

Все настройки — через переменные окружения, шаблон — [`.env.example`](.env.example).
Файл `.env` в `.gitignore` и **никогда не коммитится**.
