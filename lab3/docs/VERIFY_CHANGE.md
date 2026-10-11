# Функциональное изменение через `make verify` (п. 15)

**Автор:** Денисов Роман · **Ветка:** `lab3/deputy-filter`

**Задача (Ф1.3 ТЗ):** «Система должна отображать список всех депутатов с возможностью фильтрации».
До изменения `GET /api/v1/deputies/` возвращал всех депутатов без фильтров.

**Изменение:** параметры запроса `is_active` и `party`:

```
GET /api/v1/deputies/?is_active=true
GET /api/v1/deputies/?party=Партия А&is_active=false
```

## Порядок работы

1. Сначала написаны тесты (`tests/integration/test_deputies.py::test_filter_deputies_*`).
2. `make verify` → **упал** на шаге `test` (функции ещё нет). Политика, линтер, SAST и миграции прошли.
3. Реализован фильтр в `app/routers/deputies.py`.
4. `make verify` → **все шаги пройдены**, только после этого сделан коммит и слияние.

## Шаг 2 — `make verify` до реализации (код возврата 2)

```text
══════ make verify ══════
▶ Проверка правил проекта
✔ Политика соблюдена: без пропусков тестов, снижения порогов и исключений
▶ ruff check + ruff format --check
All checks passed!
▶ bandit (SAST)
▶ Миграции на чистой БД + alembic check
No new upgrade operations detected.
▶ pytest (unit + integration)
tests/integration/test_deputies.py:124: AssertionError
tests/integration/test_deputies.py:134: AssertionError
FAILED tests/integration/test_deputies.py::test_filter_deputies_by_active_and_party
FAILED tests/integration/test_deputies.py::test_filter_deputies_invalid_is_active
================== 2 failed, 166 passed, 1 skipped in 13.53s ===================
make[1]: *** [Makefile:62: test] Error 1
make: *** [Makefile:124: verify] Error 2
```

## Шаг 4 — `make verify` после реализации (код возврата 0)

```text
══════ make verify ══════
▶ Проверка правил проекта
✔ Политика соблюдена: без пропусков тестов, снижения порогов и исключений
▶ ruff check + ruff format --check
All checks passed!
▶ bandit (SAST)
		Low: 0  Medium: 0  High: 0
▶ Миграции на чистой БД + alembic check
No new upgrade operations detected.
▶ pytest (unit + integration)
TOTAL                          843     28    186     14    96%
======================= 168 passed, 1 skipped in 12.91s ========================
▶ mutmut: app/services.py
Мутанты: всего 42, убито 42, статусы {'ok_killed': 42} → score 100.0%
✔ Mutation score ≥ 90%
══════ ✔ Все проверки пройдены ══════
```
