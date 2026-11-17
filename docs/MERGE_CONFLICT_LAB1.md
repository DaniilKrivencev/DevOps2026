# Конфликт слияния и его разрешение (ЛР1, п. 11)

## Как возник

Две задачи по README выполнялись параллельно в отдельных ветках от одного коммита `develop` (`b8fab9d`):

| Ветка | Автор | Коммит | Изменение секции «Быстрый старт» |
|---|---|---|---|
| `feature/quickstart-docker` | Денисов Роман | `eea5882` | заменил команды на запуск через Docker Compose |
| `feature/quickstart-windows` | Герасимов Егор | `558f1c7` | оставил локальный запуск, добавил инструкцию для Windows |

Обе ветки изменили **одни и те же строки** README.md. Первая ветка слита в `develop`
без проблем (Кривенцев Даниил), при слиянии второй Git остановился:

```
$ git merge --no-ff feature/quickstart-windows
Auto-merging README.md
CONFLICT (content): Merge conflict in README.md
Automatic merge failed; fix conflicts and then commit the result.
```

Состояние файла:

```
<<<<<<< HEAD
cp .env.example .env    # задать POSTGRES_PASSWORD и APP_AUTH_USERS
make docker-up          # ...
make container-check    # ...
=======
./setup.sh          # Linux/macOS/Git Bash: ...
make run            # ...
>>>>>>> feature/quickstart-windows
```

## Как разрешён

Ни одну версию нельзя было просто выбрать (`--ours`/`--theirs`) — потерялся бы один из
способов запуска. Секция переписана вручную: два подраздела «Docker» и «Локально без Docker»,
строка для Windows из второй ветки сохранена. Маркеры конфликта удалены, затем:

```bash
git add README.md docs/MERGE_CONFLICT_LAB1.md
git commit            # коммит слияния с описанием конфликта
git log --graph --oneline -6
```

## Как повторить на защите

```bash
git checkout develop && git checkout -b demo/a && sed -i '1s/.*/# Городская Дума (A)/' README.md && git commit -am "A"
git checkout develop && git checkout -b demo/b && sed -i '1s/.*/# Городская Дума (B)/' README.md && git commit -am "B"
git checkout develop && git merge --no-ff demo/a && git merge --no-ff demo/b   # CONFLICT
# исправить README.md вручную → git add README.md → git commit
```

---

## Конфликт № 2 — через ветку разрешения `conflict/<ветка>`

После первого конфликта команда приняла правило (CONTRIBUTING.md, раздел 1.1):
конфликт не разрешается прямо в `develop`/`main`, а прогоняется через отдельную
ветку `conflict/<ветка>`, которая проверяется CI (`ci.yml`: `on: push: conflict/**`)
и сливается в `develop` обычным запросом на слияние.

| Шаг | Кто | Что |
|---|---|---|
| 1 | Кривенцев Даниил | `feature/zapusk-roles`: в таблицу адресов ЗАПУСК.md после `/health` добавлен `/api/v1/auth/me` |
| 2 | Денисов Роман | `feature/zapusk-instance` от того же `develop`: в то же место добавлен `/nginx-health` |
| 3 | Герасимов Егор | `feature/zapusk-roles` слита в `develop` без конфликта |
| 4 | Денисов Роман | `git checkout -b conflict/zapusk-instance develop` → `git merge --no-ff feature/zapusk-instance` → **CONFLICT в ЗАПУСК.md** |
| 5 | Денисов Роман | конфликт разрешён в ветке `conflict/zapusk-instance` (оставлены обе строки), коммит слияния с пометкой `Conflicts:` |
| 6 | — | `make verify`, push ветки `conflict/zapusk-instance` → CI |
| 7 | Герасимов Егор (ревью) | `conflict/zapusk-instance` → `develop` чистым слиянием `--no-ff`, без конфликтов |

```
*   слияние conflict/zapusk-instance в develop            ← develop получает готовый результат
|\
| *   разрешение конфликта ... в ветке conflict/zapusk-instance   (Conflicts: ЗАПУСК.md)
| |\
| | * ЗАПУСК.md — адрес проверки nginx /nginx-health     (feature/zapusk-instance)
* | | слияние feature/zapusk-roles в develop
```

Посмотреть: `git log --graph --oneline develop -12`, ветка `conflict/zapusk-instance` на GitHub.
