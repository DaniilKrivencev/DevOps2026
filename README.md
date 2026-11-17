# Городская Дума — City Council Management System

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

Техническое задание — [docs/ТЗ.md](docs/ТЗ.md), API — [docs/API.md](docs/API.md),
схема данных — [docs/schema.md](docs/schema.md).

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

## Быстрый старт (локально)

```bash
./setup.sh          # или make setup: venv, зависимости, .env, миграции, make verify
make run            # http://localhost:8000  (Swagger: /docs, health: /health)
make verify         # весь обязательный набор проверок
```

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
├── docs/                # ТЗ, API, схема, отчёты по лабораторным
├── Makefile             # единый интерфейс команд
└── CONTRIBUTING.md      # правила внесения изменений (GitFlow, запреты, приёмка)
```

## Лабораторные работы

| ЛР | Тема | Где смотреть |
|----|------|--------------|
| 1 | Сквозной проект и Git-процесс | [docs/ТЗ.md](docs/ТЗ.md), [docs/API.md](docs/API.md), [docs/schema.md](docs/schema.md), [CONTRIBUTING.md](CONTRIBUTING.md), тег `v0.1.0`, [docs/lab3/MERGE_CONFLICT.md](docs/lab3/MERGE_CONFLICT.md) |
| 2 | Развёртывание в Linux-среде | [docs/LAB2_DEPLOYMENT.md](docs/LAB2_DEPLOYMENT.md), `deploy/`, `Vagrantfile` |
| 3 | Автоматические проверки, миграции, бэкапы | [docs/lab3/README_LAB3.md](docs/lab3/README_LAB3.md), `make verify` |
| 4 | Контейнеризация и проверка окружения | [docs/LAB4_CONTAINERS.md](docs/LAB4_CONTAINERS.md), `make docker-up`, `make container-check` |

> История: до объединения код ЛР3 жил в каталоге `lab3/`, а в корне лежала версия ЛР1.
> Теперь в корне — единое актуальное приложение; состояние ЛР1 доступно по тегу `v0.1.0`.

## Конфигурация

Все настройки — через переменные окружения, шаблон — [`.env.example`](.env.example).
Файл `.env` в `.gitignore` и **никогда не коммитится**.
