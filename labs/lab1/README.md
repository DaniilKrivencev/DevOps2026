# Лабораторная работа №1: Сквозной проект и Git-процесс

> ## ▶ Как запустить и показать (2 минуты)
>
> **Вариант А — Docker** (Docker Desktop):
> ```bash
> cp .env.example .env          # в .env задать POSTGRES_PASSWORD и APP_AUTH_USERS=admin:<пароль>:admin
> make docker-up                # или: docker compose up -d --build --wait
> ```
> Открыть **http://localhost:8080** — веб-интерфейс, **/docs** — API, **/health** — проверка.
> При создании/удалении записей браузер спросит логин и пароль из `APP_AUTH_USERS`.
>
> **Вариант Б — без Docker** (Linux / Git Bash / ВМ): `./setup.sh && make run` →
> **http://localhost:8000**, вход `admin` / `admin` (демо-учётка только для локального запуска).
>
> **Показать Git-процесс:**
> ```bash
> git log --graph --oneline --decorate -30     # ветки feature/*, develop, release/*, слияния
> git tag                                      # v0.1.0 — первая версия
> git log --graph --oneline develop -14        # два конфликта слияния (см. MERGE_CONFLICT.md)
> ```

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

---

## ❓ Ответы на основные вопросы

**Что за система?** Учёт работы городской думы: депутаты, комиссии и их состав, заседания комиссий, повестка, посещаемость. HTTP API (FastAPI) + веб-интерфейс + PostgreSQL.

**Какие сущности и связи?** `Deputy` ↔ `Commission` — многие-ко-многим через `CommissionMember`; `Session` принадлежит комиссии; `Attendance` — явка депутата на заседание (пара «депутат + заседание» уникальна); `AgendaItem` — пункт повестки заседания. Подробно — [schema.md](schema.md).

**Какое правило предметной области?** 1) председатель комиссии обязан быть её членом (иначе 422); 2) заседание можно отметить «Проведено» только при кворуме — присутствует **больше половины** членов комиссии (`app/services.py`).

**Как устроена авторизация?** HTTP Basic. Учётные записи — переменная `AUTH_USERS="логин:пароль:роль,..."`. Чтение (GET) открыто всем; изменения: депутаты и комиссии — роль `admin`, заседания, повестка, явка — `admin` или `secretary`. Без входа — 401, нет прав — 403. Пароль сравнивается за постоянное время (`hmac.compare_digest`). В production без `AUTH_USERS` вход невозможен — демо-учёток нет.

**Как работает логирование?** `app/logging_setup.py`: каждый запрос пишется в stdout — метод, путь, код, время, request id (он же в заголовке ответа `X-Request-ID`). Необработанная ошибка — запись с трассировкой, клиенту — 500 и request id, по которому ошибку находят в журнале. Смотреть: `journalctl -u cityduma` (ЛР2), `docker compose logs app1` (ЛР4).

**Как передаются настройки?** Только переменными окружения (`app/config.py`): `DATABASE_URL`, `AUTH_USERS`, `LOG_LEVEL`… Шаблон — `.env.example`, реальные значения — `.env`, который в `.gitignore`.

**Что проверяет `/health`?** Что приложение отвечает и БД доступна (`SELECT 1`). При недоступной БД возвращает `"database": "error: ..."`.

**Что такое GitFlow у нас?** `main` — только выпущенные версии с тегами; `develop` — интеграция; `feature/*` — каждая задача; `release/*` — подготовка выпуска; `conflict/*` — разрешение конфликтов. Слияния только `--no-ff`, после `make verify` и зелёного CI.

**Как возник и разрешён конфликт?** Две ветки изменили одни и те же строки файла; при слиянии второй Git остановился с `CONFLICT`. Файл исправлен вручную с сохранением изменений обеих веток, затем коммит слияния с пометкой `Conflicts:`. Второй конфликт разрешён в отдельной ветке `conflict/zapusk-instance`, чтобы `develop` ни на минуту не был сломан. Подробно — [MERGE_CONFLICT.md](MERGE_CONFLICT.md).

**Как доказать, что секреты не в репозитории?** `cp .env.example .env && git status` — `.env` не появляется; `git check-ignore -v .env` показывает правило; gitleaks в CI проверяет всю историю.

**Зачем тег?** Тег `v0.1.0` — неизменяемая метка коммита первой версии: `git checkout v0.1.0` возвращает ровно то состояние.
