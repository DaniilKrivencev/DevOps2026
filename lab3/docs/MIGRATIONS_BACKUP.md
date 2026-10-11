# Миграции и резервное копирование (п. 8, 9, 11, 12)

**Автор:** Кривенцев Даниил

Средство миграций — **Alembic** (`alembic/`, `alembic.ini`). URL БД берётся из `app/config.py`
(`DATABASE_URL`, по умолчанию локальный SQLite); миграции работают и в PostgreSQL 16, и в SQLite.

## Последовательные изменения схемы

| Ревизия | Файл | Изменение | Автор |
|---------|------|-----------|-------|
| 0001 | `0001_initial.py` | исходная схема ЛР1: deputies, commissions, commission_members, sessions, attendances | (ЛР1) |
| 0002 | `0002_deputy_contacts.py` | `deputies.email` (уникальный), `deputies.phone` | Кривенцев Д. |
| 0003 | `0003_commission_active_session_index.py` | `commissions.is_active` (server_default true), индекс `ix_sessions_held_on` | Кривенцев Д. |
| 0004 | `0004_agenda_items.py` | новая функция «Повестка»: таблица `agenda_items` | Герасимов Е. |

Правила для миграций, чтобы они были безопасны для БД с данными:

- новые NOT NULL-столбцы — только с `server_default` (у старых строк появляется значение);
- `op.batch_alter_table` — в SQLite ALTER выполняется пересозданием таблицы;
- на время миграций в SQLite `PRAGMA foreign_keys=OFF` (см. «Найденная ошибка» ниже);
- у каждой ревизии есть рабочий `downgrade`; ENUM-типы удаляются только в PostgreSQL.

## Команды

```bash
make migrate          # alembic upgrade head
make migrate-down     # откат на одну ревизию
make migrate-status   # текущая ревизия и история
make migrate-new MSG="описание"   # новая ревизия (autogenerate)
make migrate-check    # чистая БД с нуля + alembic check (модели = миграции), входит в make verify
make seed             # демо-данные (сырой SQL по столбцам 0001 — работает на любой ревизии)
make backup           # резервная копия в backups/
make restore BACKUP=backups/dump_YYYYmmdd_HHMMSS.sql
make restore-demo     # бэкап → намеренная порча → восстановление
```

## Автоматические проверки (tests/integration/test_migrations.py)

- цепочка ревизий линейна: `0001 → 0002 → 0003 → 0004`, одна head;
- **чистая БД**: `upgrade head` создаёт все таблицы;
- **БД с данными**: `upgrade 0001` → вставка данных → `upgrade head` → данные на месте,
  `email = NULL`, `is_active = true`, `chair_id` сохранён, новая таблица работает со старыми строками;
- уникальность e-mail действует после миграции;
- `downgrade` до 0002 и до base, затем снова `upgrade head`;
- схема после миграций совпадает с ORM-моделями (`compare_metadata` → нет различий);
- PostgreSQL-вариант (`make test-pg`).

### Найденная ошибка

Тест «БД с данными» упал: после 0002 у комиссии обнулился `chair_id`.
Причина: batch-миграция в SQLite пересоздаёт `deputies` (`DROP` + `RENAME`),
а при включённых внешних ключах `DROP TABLE deputies` срабатывает как `ON DELETE SET NULL`
для `commissions.chair_id`. Исправлено в `alembic/env.py` — внешние ключи выключаются на время миграций.
Без теста на БД с данными эта потеря данных попала бы к пользователю.

## Проверка на PostgreSQL 16

### Создание чистой БД

```text
$ make migrate   # чистая БД → head
INFO  [alembic.runtime.migration] Running upgrade  -> 0001, Initial migration — create all tables.
INFO  [alembic.runtime.migration] Running upgrade 0001 -> 0002, Add contact fields to deputies (email, phone).
INFO  [alembic.runtime.migration] Running upgrade 0002 -> 0003, Add commissions.is_active and index on sessions.held_on.
INFO  [alembic.runtime.migration] Running upgrade 0003 -> 0004, New feature: session agenda items with decisions.
                List of relations
 Schema |        Name        | Type  |   Owner   
--------+--------------------+-------+-----------
 public | agenda_items       | table | duma_user
 public | alembic_version    | table | duma_user
 public | attendances        | table | duma_user
 public | commission_members | table | duma_user
 public | commissions        | table | duma_user
 public | deputies           | table | duma_user
 public | sessions           | table | duma_user
(7 rows)

$ make migrate-status
0004 (head)
```

### Обновление БД, уже содержащей данные

```text
$ alembic upgrade 0001   # схема как в ЛР1/ЛР2
INFO  [alembic.runtime.migration] Running upgrade  -> 0001, Initial migration — create all tables.
$ make seed   # данные в старой схеме
Добавлено: депутатов 3, комиссий 1, заседаний 1
$ make migrate   # обновление БД, уже содержащей данные
INFO  [alembic.runtime.migration] Running upgrade 0001 -> 0002, Add contact fields to deputies (email, phone).
INFO  [alembic.runtime.migration] Running upgrade 0002 -> 0003, Add commissions.is_active and index on sessions.held_on.
INFO  [alembic.runtime.migration] Running upgrade 0003 -> 0004, New feature: session agenda items with decisions.
$ psql — данные после обновления
 id |       full_name        | email | phone 
----+------------------------+-------+-------
  1 | Иванов Иван Иванович   |       | 
  2 | Петрова Анна Сергеевна |       | 
  3 | Сидоров Олег Петрович  |       | 
(3 rows)

        name         | chair_id | is_active 
---------------------+----------+-----------
 Комиссия по бюджету |        1 | t
(1 row)

 version_num 
-------------
 0004
(1 row)

```

Данные, созданные в схеме 0001, сохранились; новые столбцы получили значения по умолчанию.

### Восстановление после намеренного удаления и изменения (п. 12)

`scripts/restore_demo.sh` удаляет депутата, портит ФИО другого, обнуляет председателя комиссии,
затем восстанавливает БД из резервной копии (`pg_dump --clean --if-exists`, восстановление `psql -v ON_ERROR_STOP=1`):

```text
$ make restore-demo
▶ 1. Миграции и демо-данные
БД уже содержит данные — пропуск наполнения
  депутатов: 3 ['Иванов Иван Иванович', 'Петрова Анна Сергеевна', 'Сидоров Олег Петрович']
▶ 2. Резервная копия
Backup created: backups/restore_demo.sql
▶ 3. Намеренное удаление и изменение данных
  депутатов: 2 ['ИСПОРЧЕНО', 'Сидоров Олег Петрович']
▶ 4. Восстановление из backups/restore_demo.sql
Restored from: backups/restore_demo.sql
  депутатов: 3 ['Иванов Иван Иванович', 'Петрова Анна Сергеевна', 'Сидоров Олег Петрович']
✔ Данные восстановлены
```

Тот же сценарий проходит на SQLite (копия через `sqlite3` backup API), а автоматически
проверяется тестами `tests/integration/test_backup_restore.py` (удаление, изменение, отсутствующий файл, CLI).

### Тесты на PostgreSQL

```text
$ TEST_DATABASE_URL=postgresql+asyncpg://duma_user:***@localhost:5432/city_duma_test make test-pg

============================= 169 passed in 11.68s =============================
```
