# Лабораторная работа №3 — автоматические проверки, миграции и резервное копирование

> ## ▶ Как запустить и показать
>
> Linux / Git Bash / ВМ с Python 3.12 (например `vagrant up docker && vagrant ssh docker`, затем `cd /opt/cityduma-src`):
> ```bash
> ./setup.sh                    # venv + зависимости + .env + миграции + make verify
> make verify                   # ВСЕ проверки: policy → lint → sast → migrate-check → test → mutation
> make restore-demo             # бэкап → порча данных → восстановление
> make migrate-check            # миграции на чистой БД
> ```
> Отчёты после проверки: `reports/htmlcov/index.html` (покрытие), `reports/junit.xml`, `reports/mutmut.log`.

Проект «Городская Дума» (FastAPI + SQLAlchemy async + Alembic). К приложению из ЛР1/ЛР2
добавлен **единый локальный проверочный контур**: любое изменение принимается только
после `make verify`. Код выполнялся в каталоге `lab3/`, затем стал основой проекта в
корне репозитория — все команды ниже выполняются из корня.

## Быстрый старт

```bash
./setup.sh            # или make setup: venv, зависимости, .env, миграции, make verify
make run              # http://localhost:8000  (Swagger: /docs)
make verify           # весь обязательный набор проверок
```

Нужен Python 3.12+. По умолчанию используется локальный SQLite-файл `cityduma.db`;
для PostgreSQL укажите `DATABASE_URL=postgresql+asyncpg://...` в `.env`.

## Команды

| Назначение | Команда |
|---|---|
| установка / первичная настройка | `make setup`, `make install` |
| запуск | `make run` |
| проверка (всё) | **`make verify`** = `policy` → `lint` → `sast` → `migrate-check` → `test` → `mutation` |
| линтер / форматирование | `make lint`, `make format` |
| SAST | `make sast` (bandit) |
| тесты | `make test`, `make test-unit`, `make test-integration`, `make test-pg` |
| мутационное тестирование | `make mutation` |
| миграции | `make migrate`, `make migrate-down`, `make migrate-status`, `make migrate-new MSG=...`, `make migrate-check` |
| резервная копия / восстановление | `make backup`, `make restore BACKUP=backups/<файл>`, `make restore-demo` |
| демо-данные | `make seed` |

`make help` — список всех команд.

## Выполнение задания

| № | Пункт | Где |
|---|---|---|
| 1 | единый сценарий первоначальной настройки | `setup.sh`, `make setup` |
| 2 | зафиксированные версии | `requirements.txt`, `requirements-dev.txt` (`==`), `.python-version` |
| 3 | команды установки, запуска, проверки, миграций, бэкапа, восстановления | `Makefile` |
| 4 | unit- и интеграционные тесты (≥ 40% ТЗ) | `tests/` — 169 тестов, 17/17 требований ТЗ, покрытие кода 96% → [TESTING.md](TESTING.md) |
| 5 | ошибочные данные, границы, обязательные правила, мутационное тестирование | `tests/unit/test_services.py`, `test_schemas.py`, `make mutation` (100%) |
| 6 | отдельная тестовая конфигурация и изоляция данных | `app/config.py` (`APP_ENV=test`), `tests/conftest.py` (своя БД на каждый тест) |
| 7 | линтер, SAST, отчёты тестов и покрытия | ruff, bandit, `reports/junit.xml`, `reports/htmlcov`, `reports/coverage.xml` |
| 8 | средство миграций, ≥ 3 последовательных изменения | Alembic, ревизии `0002`, `0003`, `0004` → [MIGRATIONS_BACKUP.md](MIGRATIONS_BACKUP.md) |
| 9 | чистая БД и обновление БД с данными | `tests/integration/test_migrations.py`, `make migrate-check`, журнал PostgreSQL |
| 10 | новая функция, требующая изменения схемы | «Повестка заседания»: миграция `0004`, `app/routers/agenda.py` |
| 11 | команды резервного копирования и восстановления | `scripts/db_backup.py`, `make backup` / `make restore` |
| 12 | восстановление после намеренного удаления/изменения | `make restore-demo`, `tests/integration/test_backup_restore.py` |
| 13 | единая команда `make verify` | `Makefile` |
| 14 | запрет пропуска тестов, снижения порогов, исключений без обоснования | `scripts/check_policy.py` (`make policy`), [CONTRIBUTING.md](../../CONTRIBUTING.md) |
| 15 | функциональное изменение через `make verify` | фильтр депутатов → [VERIFY_CHANGE.md](VERIFY_CHANGE.md) |

Конфликт слияния и слияния ЛР1–ЛР3: [MERGE_CONFLICT.md](MERGE_CONFLICT.md).

## Структура

```
. (корень репозитория)
├── setup.sh                 # единый сценарий настройки
├── Makefile                 # все команды, make verify
├── requirements*.txt        # зафиксированные версии
├── pyproject.toml           # pytest, coverage (порог 85%), ruff, bandit, mutmut
├── app/
│   ├── config.py            # окружения development / production / test
│   ├── services.py          # бизнес-правила (кворум, председатель, повестка)
│   └── routers/agenda.py    # новая функция ЛР3
├── alembic/versions/        # 0001 … 0004
├── scripts/
│   ├── db_backup.py         # backup / restore (PostgreSQL и SQLite)
│   ├── restore_demo.sh      # демонстрация восстановления
│   ├── seed.py              # демо-данные
│   ├── check_policy.py      # правила п. 14
│   └── check_mutation.py    # порог mutation score
├── tests/unit/              # 94 теста
├── tests/integration/       # 75 тестов
└── labs/lab3/               # отчёты (этот каталог)
```

## Кто что делал

| Участник | Вклад |
|---|---|
| **Герасимов Егор** | перенос проекта и фиксация версий, `setup.sh`, конфигурация окружений, `Makefile` и `make verify`, тестовая конфигурация и изоляция, SAST и правила ruff, политика запретов (п. 14) и CONTRIBUTING, мутационное тестирование, новая функция «Повестка» с миграцией 0004, разрешение конфликта слияния, документация (README, конфликт слияния); слияние ЛР2 |
| **Кривенцев Даниил** | миграции 0002 и 0003, команды backup/restore, тесты миграций (чистая БД, БД с данными, откат, дрейф схемы) — найдена и исправлена потеря данных в SQLite, демонстрация восстановления, документация по миграциям и бэкапам; изменение ЛР2 (healthcheck), слияние ЛР1 |
| **Денисов Роман** | вынос бизнес-правил в `services.py`, unit-тесты и граничные случаи, валидация схем, интеграционные тесты API и БД — найдены и исправлены ошибки каскадного удаления, отчёты тестов и порог покрытия, функциональное изменение через `make verify`, документация по тестированию; изменение ЛР1 (`.env.example`) |

Подробно — в истории: `git log --graph --format='%h %an: %s' -- lab3`.

---

## ❓ Ответы на основные вопросы

**Что делает каждый шаг `make verify`?** `policy` — нет пропущенных тестов, сниженных порогов, исключений анализаторов без обоснования; `lint` — стиль и типичные ошибки (ruff); `sast` — поиск уязвимостей в коде (bandit); `migrate-check` — миграции с нуля на чистой БД и совпадение моделей с миграциями (`alembic check`); `test` — unit + интеграционные тесты, отчёты и порог покрытия 85%; `mutation` — мутационное тестирование, порог 90%.

**Чем unit-тесты отличаются от интеграционных?** Unit — чистая логика без БД (`tests/unit`: правила кворума, председателя, схемы данных). Интеграционные — через настоящий API и реальную БД (`tests/integration`: CRUD, миграции, бэкапы).

**Что такое мутационное тестирование?** mutmut автоматически вносит маленькие ошибки в бизнес-правила (`>` → `>=`, `+1` → `+2`…) и запускает тесты. Каждая «мутация» должна быть поймана тестом. У нас 42/42 — значит, тесты реально проверяют логику. Если преподаватель поменяет условие кворума, упадёт `tests/unit/test_services.py`.

**Как изолированы тестовые данные?** `APP_ENV=test` выставляется до запуска приложения — рабочая БД не используется; каждый тест получает свою чистую БД (временный файл SQLite или пересоздаваемая схема в PostgreSQL через `TEST_DATABASE_URL`).

**Какие миграции?** 0001 — исходная схема; 0002 — контакты депутатов (email, телефон); 0003 — активность комиссий и индекс по дате заседаний; 0004 — повестка заседания (новая функция). Проверены на чистой БД и на БД с данными (`tests/integration/test_migrations.py`, `make migrate-check-pg`).

**Как работают бэкапы?** `make backup` — для PostgreSQL `pg_dump`, для SQLite — копия файла; `make restore BACKUP=...` — восстановление. `make restore-demo` показывает: бэкап → удаление и порча данных → восстановление → сравнение с исходными данными.

**Что запрещено и как это проверяется?** Пропуск тестов, снижение порогов, `# noqa`/`# nosec` без обоснования, удаление шага из verify — ловит `scripts/check_policy.py`. Правила записаны в `CONTRIBUTING.md`.
