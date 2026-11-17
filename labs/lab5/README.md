# Лабораторная работа №5: Continuous Integration

## 1. Выбор системы и подключение

| Что | Решение | Почему |
|---|---|---|
| CI-система | **GitHub Actions** | репозиторий уже на GitHub; не требует своего сервера (GitLab — ~16 ГБ ОЗУ) |
| Registry | **GitHub Container Registry** `ghcr.io/daniilkrivencev/devops2026` | встроен в GitHub, доступ по `GITHUB_TOKEN` без хранения паролей |
| Исполнение проверок | **Docker-in-Docker**: сервис `docker:29.9.0-dind` в каждом job | требование от 12.11.2026 — все проверки в DinD |

Файлы: [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) (граф этапов),
[`.github/workflows/ci-stage.yml`](../../.github/workflows/ci-stage.yml) (один этап в DinD),
[`scripts/ci.sh`](../../scripts/ci.sh) (команды этапов), [`.github/CODEOWNERS`](../../.github/CODEOWNERS),
[`scripts/acceptance_guard.py`](../../scripts/acceptance_guard.py).

## 2. Pipeline

```
push (main, develop, feature/**, release/**, hotfix/**, теги v*) · pull_request (в main, develop)
 │
 ├─ 0. guard       критические файлы приёмки, запрет удаления тестов
 ├─ 1. style       make policy lint
 ├─ 2. test        make test на отдельной тестовой БД PostgreSQL + make mutation
 ├─ 3. migrations  make migrate-check (чистая БД) + make migrate-check-pg (БД с данными, откат)
 ├─ 4. backup      make restore-demo на PostgreSQL: бэкап → порча данных → восстановление
 ├─ 5. security    make sast (bandit) + make audit (pip-audit) + gitleaks (секреты, вся история)
 ├─ 6. build       образ ghcr.io/…:sha-<12 символов SHA> → артефакт image.tar.gz
 │     └─ 7. container   make container-check на ЭТОМ образе + trivy (уязвимости образа)
 │
 └─ 8. publish     needs: [0…7] и только push в main / тег vX.Y.Z → docker push
```

Каждый этап — отдельный job (`ci-stage.yml`), в котором:

1. запускается сервис `docker:dind` (TLS, порт 2376); раннер работает только как клиент
   (`DOCKER_HOST=tcp://localhost:2376`), **все контейнеры создаёт демон DinD**;
2. образ инструментов `cityduma-ci:<хэш зависимостей>` (`Dockerfile`, `--target ci`:
   Python, dev-зависимости, make, клиент PostgreSQL 16) берётся из кэша или собирается;
3. `scripts/ci.sh <этап>` выполняет в этом контейнере **те же цели Makefile**, что и разработчик;
4. отчёты из `reports/` сохраняются как артефакты `reports-<этап>`.

## 3. Выполнение требований

| № | Требование | Реализация |
|---|---|---|
| 1 | Выбор CI | GitHub Actions (обоснование — раздел 1) |
| 2 | Репозиторий и registry | workflow в репозитории; публикация в `ghcr.io` (допускается и локальный registry: `REGISTRY=localhost:5000 scripts/ci.sh publish`) |
| 3 | Запуск при push, MR и изменении основной ветки | `on: push` (все ветки GitFlow и теги `v*`), `pull_request` в `main`/`develop` |
| 4 | Те же команды, что локально | `scripts/ci.sh` вызывает `make policy lint test mutation migrate-check sast audit container-check …`; локально `make ci` / `make ci-<этап>` |
| 5 | Этапы | guard, стиль, тесты, миграции, резервное копирование, безопасность, сборка, контейнерная проверка, публикация |
| 6 | Всё в DinD | сервис `docker:dind` в каждом job; тесты, БД, сборка, compose-стенд, сканеры — контейнеры внутри DinD |
| 7 | Отдельная тестовая БД | одноразовый `postgres:16.16-alpine` в tmpfs, своя сеть и случайный пароль на каждый запуск; `TEST_DATABASE_URL` используется только при `APP_ENV=test` |
| 8 | Отчёты | JUnit (`junit.xml`), покрытие (`coverage.xml`, `htmlcov/`), mutmut, bandit, pip-audit, gitleaks, trivy, журналы стенда — артефакты `reports-<этап>` |
| 9 | Кэширование зависимостей | `actions/cache`: образ инструментов с установленными зависимостями (`docker save`), ключ — хэш `Dockerfile` и `requirements*` |
| 10 | Тег по commit SHA | `sha-<первые 12 символов SHA>`; для тега `vX.Y.Z` — ещё `X.Y.Z`; `latest` не используется |
| 11 | Нет публикации при ошибке | `publish.needs` — все обязательные этапы; публикуется ровно тот образ, что прошёл `container-check` и trivy |
| 12 | Секреты в защищённых переменных | registry — `secrets.GITHUB_TOKEN` (передаётся только в этап publish); пароли тестовых БД генерируются на лету; в репозитории секретов нет |
| 13 | Секреты, зависимости, образ | gitleaks (`.gitleaks.toml`, вся история), pip-audit (`requirements.lock`, ошибка при уязвимости), trivy (CRITICAL с исправлением — ошибка, полный отчёт HIGH/CRITICAL в `trivy.txt`) |
| 14–15 | Защита критических файлов | `CODEOWNERS` + правило защиты веток (раздел 5) + этап `guard` |
| 16 | Ослабление не проходит незаметно | удаление теста → `guard` красный; снижение порога / `noqa` без обоснования → `make policy` красный; `latest`/root/отключённый healthcheck → `container-lint` красный; правка workflow → обязательное ревью владельца |
| 17 | Зелёный CI для корректного изменения и красный для дефектного | раздел 6 |

Зависимости обновлены перед включением строгого `pip-audit`: было 11 известных уязвимостей
(starlette, jinja2, python-dotenv) — см. коммит «обновление уязвимых зависимостей».

## 4. Совпадение локальных и серверных проверок

```bash
make verify          # быстрый локальный контур (venv)
make ci              # весь pipeline локально в контейнерах — тот же scripts/ci.sh, что в CI
make ci-test         # один этап
```

Почему это важно: CI — независимый барьер, но если в нём выполняются другие команды,
то «локально зелёное» не гарантирует «в CI зелёное» и наоборот: разработчик не может
воспроизвести падение, а проверки расходятся (configuration drift). Один `Makefile`,
одни версии инструментов (`requirements-dev.txt`, образ `cityduma-ci`) и один сценарий
`scripts/ci.sh` дают одинаковый результат на ноутбуке и на сервере.

## 5. Защита критических файлов

1. **CODEOWNERS** — у тестов, `Makefile`, `pyproject.toml`, правил проверок, workflow, Dockerfile,
   миграций и зависимостей указаны владельцы.
2. **Защита веток** (настраивает владелец репозитория: *Settings → Branches → Add rule* для `main` и `develop`):
   - Require a pull request before merging → Require approvals: 1 → **Require review from Code Owners**;
   - Require status checks to pass → выбрать все этапы `CI` (guard, style, test, …, container);
   - Do not allow bypassing the above settings; запрет force push.
3. **Этап guard** (`scripts/acceptance_guard.py`): список изменённых критических файлов в отчёте job'а;
   уменьшение числа тестов останавливает pipeline, если на PR нет метки `allow-test-removal`.
4. **Политики**: `scripts/check_policy.py` (пропуск тестов, пороги, исключения анализаторов),
   `scripts/container_policy.py` (latest, root, секреты, healthcheck, порты).

## 6. Демонстрация на защите

Ветка для демонстраций: `git checkout -b feature/ci-demo develop`.

**1. Сломать тест или миграцию → pipeline останавливается**
```bash
# бизнес-правило кворума: > 50% → >= 50%
sed -i 's/present \* 2 > total/present * 2 >= total/' app/services.py
git commit -am "demo: дефект в правиле кворума" && git push -u origin feature/ci-demo
```
Actions: `2. Тесты` — красный (тест кворума и мутационный порог), `8. Публикация` — не запускается.
Вариант с миграцией: в новой ревизии сослаться на несуществующую колонку → красный `3. Миграции`.

**2. Тестовый секрет обнаруживается**
```bash
# секрет генерируется на месте и в репозиторий заранее не кладётся
python3 -c "import secrets,string; print('GITHUB_TOKEN=ghp_' + ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(36)))" > leak.env.txt
git add leak.env.txt && git commit -m "demo: секрет" && git push
```
`5. Безопасность` → gitleaks: `RuleID: github-pat, File: leak.env.txt`; отчёт `reports-security/gitleaks.json`.
После демонстрации: `git revert HEAD` (секрет считается скомпрометированным — его нужно отозвать).

**3. После ошибки образ не публикуется**: в графе job'ов `8. Публикация` в состоянии *skipped*;
в *Packages* нет образа с `sha-<этот коммит>`. Публикация возможна только из `main` и тегов.

**4. Защита критических файлов**
```bash
git rm tests/unit/test_services.py && git commit -m "demo: удаляю тесты" && git push
```
`0. Защита файлов приёмки` — красный: «количество тестов уменьшилось». В PR GitHub требует
ревью владельца из CODEOWNERS, кнопка Merge заблокирована. Снижение `fail_under` в
`pyproject.toml` → красный `1. Стиль` (`make policy`).

**5. Корректное изменение → всё зелёное**: изменение README или новая функция с тестами —
все этапы зелёные; при слиянии в `main` появляется образ `ghcr.io/daniilkrivencev/devops2026:sha-…`.

## 7. Локальный запуск этапов

```bash
make ci-guard ci-style ci-test ci-migrations ci-backup ci-security ci-build ci-container
make ci                       # все подряд
```

Нужен только Docker: Python-инструменты, PostgreSQL и сканеры запускаются в контейнерах.
