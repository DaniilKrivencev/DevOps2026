# Слияние веток и конфликт слияния

**Автор:** Герасимов Егор

## Что такое слияние и конфликт слияния

**Слияние (merge)** объединяет историю двух веток. Git находит общего предка
(*merge base*) и сравнивает с ним обе ветки:

- изменения в **разных** файлах или в **разных фрагментах** одного файла
  Git объединяет сам (*auto-merge*);
- если обе ветки изменили **один и тот же фрагмент** (те же или соседние строки)
  по-разному, Git не знает, какой вариант правильный, — это **конфликт слияния**.
  Слияние останавливается, а в файле появляются маркеры:

```text
<<<<<<< HEAD          ← версия текущей ветки (куда сливаем)
...
=======
...
>>>>>>> lab3/tests    ← версия сливаемой ветки
```

Разрешение конфликта: вручную привести фрагмент к правильному виду (часто — объединить
обе версии), удалить маркеры, проверить (`make verify`), выполнить `git add` и `git commit`.
Коммит слияния имеет двух родителей и сохраняет историю обеих веток.

`git merge --no-ff` создаёт коммит слияния даже когда возможна «перемотка» (fast-forward) —
так в истории видно, какие коммиты пришли из какой ветки и кто выполнил слияние.

## Конфликт в ЛР3 (реальный)

Две ветки были созданы от одного коммита `c34292c` (каркас ЛР3) и велись параллельно:

| Ветка | Автор | Что изменила в `lab3/Makefile` |
|-------|-------|-------------------------------|
| `lab3/migrations` | Кривенцев Даниил | `.PHONY` + цели `migrate-check`, `seed`, `backup`, `restore`, `restore-demo`; шаг `migrate-check` в `verify` |
| `lab3/tests` | Денисов Роман | `.PHONY` + цели `test-unit`, `test-integration`, `test-pg`; отчёты и покрытие в `test` |

`lab3/migrations` слита первой (`8ab15eb`). При слиянии `lab3/tests`:

```text
$ git merge --no-ff lab3/tests
Auto-merging lab3/Makefile
CONFLICT (content): Merge conflict in lab3/Makefile
Auto-merging lab3/app/models.py
Auto-merging lab3/app/schemas.py
Automatic merge failed; fix conflicts and then commit the result.

$ git status --short
UU lab3/Makefile
```

Конфликтный фрагмент — обе ветки переписали одну и ту же строку `.PHONY`:

```makefile
<<<<<<< HEAD
.PHONY: help setup install run lint format test migrate migrate-down migrate-status \
        migrate-new migrate-check \
        seed backup restore restore-demo verify clean
=======
.PHONY: help setup install run lint format test test-unit test-integration test-pg \
        migrate migrate-down migrate-status migrate-new verify clean
>>>>>>> lab3/tests
```

Остальные изменения Git слил сам: в `Makefile` — новые цели и шаги `verify` (разные фрагменты),
в `models.py` (поля e-mail/телефон от Даниила и `passive_deletes` от Романа) и в `schemas.py`.

**Разрешение** (Герасимов Егор, коммит `3bdf47c`): нужны цели обеих веток, поэтому строки объединены:

```makefile
.PHONY: help setup install run lint format test test-unit test-integration test-pg \
        migrate migrate-down migrate-status migrate-new migrate-check \
        seed backup restore restore-demo verify clean
```

Затем `make verify` — 115 тестов прошли, покрытие 95% — и коммит слияния с описанием конфликта.

```text
*   3bdf47c Герасимов Егор: ЛР3 — слияние lab3/tests с разрешением конфликта в Makefile
|\
| * f4b5f55 Денисов Роман: ЛР3 — отчёты тестов и покрытия, порог покрытия 85%
| * acc8fdf Денисов Роман: ЛР3 — интеграционные тесты API и БД, исправлены каскадные удаления
| * c9ecd8b Денисов Роман: ЛР3 — проверки ошибочных данных и граничных значений в схемах
| * 24e0fb3 Денисов Роман: ЛР3 — бизнес-правила вынесены в app/services.py + unit-тесты
* |   8ab15eb Герасимов Егор: ЛР3 — слияние lab3/migrations (миграции 0002–0003, бэкапы)
|\ \
| |/
|/|
| * aaf433c Кривенцев Даниил: ЛР3 — восстановление после намеренного удаления/изменения данных
| * ...
|/
*   c34292c Герасимов Егор: ЛР3 — слияние каркаса lab3/skeleton
```

## Слияния в ЛР1 и ЛР2

| Лаба | Ветка | Автор изменений | Слияние выполнил | Коммит слияния |
|------|-------|-----------------|------------------|----------------|
| ЛР1 | `lab1/fix-env-example` — `.env.example` приведён к переменным `docker-compose.yml` | Денисов Роман | Кривенцев Даниил | `b41c6ce` |
| ЛР2 | `lab2/healthcheck-retry` — проверка `/health` с повторами в `deploy_app.sh` + пункт чек-листа | Кривенцев Даниил | Герасимов Егор | `64d584d` |

## Все слияния ЛР3

| Ветка | Содержание | Автор | Слил |
|-------|-----------|-------|------|
| `lab3/skeleton` | каркас, setup.sh, Makefile, тестовая конфигурация | Герасимов Е. | Герасимов Е. |
| `lab3/migrations` | миграции 0002–0003, бэкапы, тесты миграций | Кривенцев Д. | Герасимов Е. |
| `lab3/tests` | бизнес-правила, unit/интеграционные тесты, покрытие — **конфликт** | Денисов Р. | Герасимов Е. |
| `lab3/contacts-tests` | тесты полей 0002/0003 | Кривенцев Д. | Денисов Р. |
| `lab3/quality` | SAST, политика, мутационное тестирование | Герасимов Е. | Кривенцев Д. |
| `lab3/agenda` | новая функция + миграция 0004 | Герасимов Е. | Денисов Р. |
| `lab3/deputy-filter` | изменение через make verify | Денисов Р. | Герасимов Е. |
| `lab3/docs-*` | документация | все | все |

## Как воспроизвести конфликт самостоятельно (на защите)

```bash
git switch -c demo/a main
sed -i 's/^verify: ## .*/verify: ## Проверки (вариант A)/' lab3/Makefile
git commit -am "demo: вариант A"

git switch -c demo/b main
sed -i 's/^verify: ## .*/verify: ## Проверки (вариант B)/' lab3/Makefile
git commit -am "demo: вариант B"

git switch demo/a
git merge demo/b          # CONFLICT (content): Merge conflict in lab3/Makefile
git diff                  # видны маркеры <<<<<<< ======= >>>>>>>
# отредактировать файл, оставить нужный вариант
git add lab3/Makefile && git commit    # коммит слияния
# или отменить: git merge --abort
```

Полезные команды: `git log --oneline --graph --all`, `git merge --abort`,
`git checkout --ours/--theirs <файл>`, `git diff --name-only --diff-filter=U`.
