# Лабораторная работа №3 — автоматические проверки, миграции и резервное копирование

Проект «Городская Дума» (FastAPI + SQLAlchemy async + Alembic). Каталог `lab3/` —
самостоятельная копия приложения из ЛР1/ЛР2, к которой добавлен **единый локальный
проверочный контур**: любое изменение принимается только после `make verify`.

## Быстрый старт

```bash
cd lab3
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
| 4 | unit- и интеграционные тесты (≥ 40% ТЗ) | `tests/` — 169 тестов, 17/17 требований ТЗ, покрытие кода 96% → [docs/TESTING.md](docs/TESTING.md) |
| 5 | ошибочные данные, границы, обязательные правила, мутационное тестирование | `tests/unit/test_services.py`, `test_schemas.py`, `make mutation` (100%) |
| 6 | отдельная тестовая конфигурация и изоляция данных | `app/config.py` (`APP_ENV=test`), `tests/conftest.py` (своя БД на каждый тест) |
| 7 | линтер, SAST, отчёты тестов и покрытия | ruff, bandit, `reports/junit.xml`, `reports/htmlcov`, `reports/coverage.xml` |
| 8 | средство миграций, ≥ 3 последовательных изменения | Alembic, ревизии `0002`, `0003`, `0004` → [docs/MIGRATIONS_BACKUP.md](docs/MIGRATIONS_BACKUP.md) |
| 9 | чистая БД и обновление БД с данными | `tests/integration/test_migrations.py`, `make migrate-check`, журнал PostgreSQL |
| 10 | новая функция, требующая изменения схемы | «Повестка заседания»: миграция `0004`, `app/routers/agenda.py` |
| 11 | команды резервного копирования и восстановления | `scripts/db_backup.py`, `make backup` / `make restore` |
| 12 | восстановление после намеренного удаления/изменения | `make restore-demo`, `tests/integration/test_backup_restore.py` |
| 13 | единая команда `make verify` | `Makefile` |
| 14 | запрет пропуска тестов, снижения порогов, исключений без обоснования | `scripts/check_policy.py` (`make policy`), [CONTRIBUTING.md](CONTRIBUTING.md) |
| 15 | функциональное изменение через `make verify` | фильтр депутатов → [docs/VERIFY_CHANGE.md](docs/VERIFY_CHANGE.md) |

Конфликт слияния и слияния ЛР1–ЛР3: [docs/MERGE_CONFLICT.md](docs/MERGE_CONFLICT.md).

## Структура

```
lab3/
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
└── docs/                    # отчёты
```

## Кто что делал

| Участник | Вклад |
|---|---|
| **Герасимов Егор** | перенос проекта и фиксация версий, `setup.sh`, конфигурация окружений, `Makefile` и `make verify`, тестовая конфигурация и изоляция, SAST и правила ruff, политика запретов (п. 14) и CONTRIBUTING, мутационное тестирование, новая функция «Повестка» с миграцией 0004, разрешение конфликта слияния, документация (README, конфликт слияния); слияние ЛР2 |
| **Кривенцев Даниил** | миграции 0002 и 0003, команды backup/restore, тесты миграций (чистая БД, БД с данными, откат, дрейф схемы) — найдена и исправлена потеря данных в SQLite, демонстрация восстановления, документация по миграциям и бэкапам; изменение ЛР2 (healthcheck), слияние ЛР1 |
| **Денисов Роман** | вынос бизнес-правил в `services.py`, unit-тесты и граничные случаи, валидация схем, интеграционные тесты API и БД — найдены и исправлены ошибки каскадного удаления, отчёты тестов и порог покрытия, функциональное изменение через `make verify`, документация по тестированию; изменение ЛР1 (`.env.example`) |

Подробно — в истории: `git log --graph --format='%h %an: %s' -- lab3`.
