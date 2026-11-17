# Лабораторная работа №1: Сквозной проект и Git-процесс

## Материалы в этом каталоге

| Файл | Что это |
|---|---|
| [ТЗ.md](ТЗ.md) | техническое задание (ГОСТ 19.201-78 / 34.602-89) |
| [API.md](API.md) | описание HTTP API, коды ответов, авторизация |
| [schema.md](schema.md) | схема данных: сущности, связи, ограничения |
| [MERGE_CONFLICT.md](MERGE_CONFLICT.md) | два конфликта слияния и их разрешение (второй — через ветку `conflict/…`) |
| [git_workflow_demo.sh](git_workflow_demo.sh) | сценарий демонстрации Git-процесса |

Конфликт слияния времён ЛР3 описан в [../lab3/MERGE_CONFLICT.md](../lab3/MERGE_CONFLICT.md).

## Файлы проекта

| Файл / каталог | Назначение |
|---|---|
| [`app/`](../../app) | FastAPI-приложение: API, веб-интерфейс (`app/templates/`), `/health` |
| [`app/auth.py`](../../app/auth.py) | базовая авторизация HTTP Basic, роли `admin` / `secretary` |
| [`app/logging_setup.py`](../../app/logging_setup.py) | журналирование запросов и ошибок |
| [`app/services.py`](../../app/services.py) | правила предметной области (председатель, кворум) |
| [`alembic/`](../../alembic) | схема БД (PostgreSQL) |
| [`README.md`](../../README.md), [`.gitignore`](../../.gitignore), [`.env.example`](../../.env.example) | обязательные файлы репозитория |
| [`CONTRIBUTING.md`](../../CONTRIBUTING.md) | правила внесения изменений: GitFlow, обязательные проверки, запреты, приёмка |

## Выполнение задания

| № | Пункт | Где |
|---|---|---|
| 1–3 | Предметная область, сценарии, ТЗ по ГОСТ | [ТЗ.md](ТЗ.md) |
| 4 | Приложение с HTTP API, реляционной БД и веб-интерфейсом | `app/`, PostgreSQL, `/ui/*` |
| 5 | Логирование ошибок | `app/logging_setup.py`: каждый запрос, ошибки с трассировкой, request id |
| 6 | Базовая авторизация | `app/auth.py`: чтение открыто, изменения — `admin`/`secretary` (401/403) |
| 7 | ≥ 3 связанных сущности, правило предметной области | депутаты, комиссии, заседания, посещаемость, повестка; кворум, председатель |
| 8 | Обработка некорректных запросов, env-конфигурация, health | 422/404/409, `app/config.py`, `GET /health` |
| 9 | Репозиторий: README, .gitignore, .env.example, API, схема | корень + [API.md](API.md), [schema.md](schema.md) |
| 10 | Задача → ветка → коммиты → запрос на слияние, GitFlow | ветки `feature/*`, `develop`, `release/*`, `main`; `git log --graph` |
| 11 | Конфликт слияния и его разрешение | [MERGE_CONFLICT.md](MERGE_CONFLICT.md) |
| 12 | Тег первой версии | `v0.1.0` |
| 13 | Правила внесения изменений | [`CONTRIBUTING.md`](../../CONTRIBUTING.md) |

## Проверка на защите

```bash
# путь изменения от задачи до тега
git log --graph --oneline --decorate v0.1.0
git log --graph --oneline --decorate main -25

# небольшое изменение через ветку и запрос на слияние
git checkout -b feature/small-change develop
# … правка … ; make verify
git commit -am "…" && git push -u origin feature/small-change   # затем PR в develop на GitHub

# секреты и локальные файлы не попадают в репозиторий
cp .env.example .env && git status --short          # .env не появляется
git check-ignore -v .env .venv deploy/secrets.env   # правило .gitignore для каждого
```
