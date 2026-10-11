# Тестирование (п. 4–7)

**Автор:** Денисов Роман

## Состав

| Набор | Где | Кол-во | Что проверяет |
|-------|-----|--------|---------------|
| unit | `tests/unit/` | 94 | бизнес-правила (`app/services.py`), валидация схем, конфигурация, политика проверок |
| integration | `tests/integration/` | 75 | API + реальная БД, каскады и ограничения, миграции, бэкап/восстановление, веб-интерфейс |
| **всего** | | **169** | покрытие кода **96%** (порог 85%), mutation score **100%** (порог 90%) |

Запуск: `make test` (всё + отчёты), `make test-unit`, `make test-integration`,
`make test-pg` (те же тесты на PostgreSQL), `make mutation`.

Отчёты (`reports/`, не коммитятся): `junit.xml`, `coverage.xml`, `htmlcov/index.html`,
`bandit.json`, `mutmut.log`.

## Тестовая конфигурация и изоляция данных (п. 6)

- `tests/conftest.py` выставляет `APP_ENV=test` **до** импорта приложения → `app/config.py`
  в тестовом окружении игнорирует рабочий `DATABASE_URL` (проверяется `tests/unit/test_config.py`);
- каждый тест получает **свою чистую БД**: отдельный SQLite-файл во временном каталоге pytest,
  либо — при `TEST_DATABASE_URL=postgresql+...` — схема пересоздаётся перед каждым тестом;
- данные создаются фабриками `make_deputy`, `make_commission`, `make_session`;
  тест `test_list_is_empty_in_fresh_db` проверяет, что данные одного теста не видны другому.

## Покрытие функционала ТЗ (требование — не менее 40%)

| Требование ТЗ | Тесты | |
|---|---|---|
| Ф1.1 CRUD депутатов | `test_deputies.py`: create/get/update/delete, 404 | ✔ |
| Ф1.2 поля депутата | `test_create_and_get_deputy`, `test_schemas.py` (границы длины, e-mail, телефон) | ✔ |
| Ф1.3 список с фильтрацией | `test_list_deputies_ordered`, `test_filter_deputies_*` | ✔ |
| Ф2.1 CRUD комиссий | `test_commissions.py`: create/get/update/delete, 404 | ✔ |
| Ф2.2 уникальное название | `test_commission_name_unique`, `test_rename_to_existing_name_conflict` | ✔ |
| Ф2.3 состав комиссии | `test_member_duplicate`, `test_list_and_remove_member`, `test_member_unknown_entities` | ✔ |
| Ф2.4 председатель — член комиссии | `test_chair_must_be_member`, `test_chair_as_member`, `test_create_commission_with_chair_rejected`, `test_cannot_remove_chair_from_members`, unit `chair_allowed` | ✔ |
| Ф3.1 регистрация заседаний | `test_create_session_defaults`, `test_create_session_unknown_commission`, сортировка | ✔ |
| Ф3.2 статусы заседания | `test_cancel_session_without_quorum_allowed`, `test_session_unknown_status_rejected` | ✔ |
| Ф3.3 кворум > 50% | `test_quorum_exactly_half_fails` (2/4), `test_quorum_more_than_half_succeeds` (3/4), `test_quorum_without_members`, unit `has_quorum` — 13 граничных пар | ✔ |
| Ф4.1 фиксация явки | `test_attendance_update_and_delete`, `test_attendance_unknown_refs` | ✔ |
| Ф4.2 статусы явки | `test_attendance_invalid_status`, unit `attendance_rate` | ✔ |
| Ф4.3 одна запись на пару | `test_attendance_duplicate` | ✔ |
| Ф4.4 фильтры посещаемости | `test_attendance_filters` | ✔ |
| Ф5.1 `/health` | `test_health`, `test_health_reports_database_error` | ✔ |
| Ф5.2 веб-интерфейс | `test_ui_pages_render` (5 страниц) | ✔ |
| Ф5.3 OpenAPI | `test_openapi_docs_available` | ✔ |
| 4.1 ограничения и каскады | `test_delete_commission_cascades`, `test_delete_chair_deputy_sets_null`, `test_delete_deputy_with_membership_and_attendance`, `test_delete_session_cascades_attendance` | ✔ |
| 4.2 миграции, бэкап, восстановление | `test_migrations.py`, `test_backup_restore.py` | ✔ |
| Новая функция ЛР3: повестка | `test_agenda.py`, unit `decision_allowed` | ✔ |

Покрыто **17 из 17** функциональных требований (100%) + ограничения хранения и новая функция.

## Ошибочные данные, граничные случаи, обязательные правила (п. 5)

- пустые и состоящие из пробелов строки, неизвестные значения ENUM, неверные даты;
- границы длины по столбцам БД: N символов — принято, N+1 — 422;
- кворум: 0 из 0, ровно 50% (1/2, 2/4, 5/10, 50/101) — нет; 51/101, 3/4 — есть;
  согласованность `quorum_threshold` и `has_quorum` для 1..29 членов;
- ссылки на несуществующие объекты → 404, дубликаты → 409, нарушения бизнес-правил → 422.

### Мутационное тестирование

`make mutation` запускает **mutmut** по `app/services.py` (там вся бизнес-логика) и требует
mutation score ≥ 90%. Мутант — копия кода с маленькой ошибкой (`>` → `>=`, `200` → `201`,
другой текст исключения); если тесты не падают, мутант «выжил» и тесты слабые.
Первый прогон нашёл 7 выживших мутантов (83%); после усиления тестов — 42/42 (100%).
Подробности в истории коммитов (`git log --grep mutmut`).

### Ошибки, найденные тестами

| Ошибка | Нашёл тест | Исправление |
|---|---|---|
| удаление комиссии с заседаниями → 500 | `test_delete_commission_cascades` | `passive_deletes=True` |
| удаление депутата с членствами → 500 | `test_delete_deputy_with_membership_and_attendance` | `passive_deletes=True` |
| комиссию можно создать сразу с председателем-«не членом» (нарушение Ф2.4) | `test_create_commission_with_chair_rejected` | 422 при создании |
| повторное название комиссии → 500 | `test_commission_name_unique` | 409 |
| миграция 0002 в SQLite обнуляла `chair_id` | `test_upgrade_database_with_existing_data` | `PRAGMA foreign_keys=OFF` на время миграций |
