# Лабораторная работа №6: Continuous Delivery и проверка работающего релиза

## 1. Схема доставки

```
 push в main / тег vX.Y.Z
        │
        ▼
 CI (ЛР5): guard → style → test → migrations → backup → security → build → container
        │  все этапы зелёные → publish: ghcr.io/daniilkrivencev/devops2026:sha-<commit> (и X.Y.Z для тега)
        ▼
 CD (.github/workflows/cd.yml)   environment «staging» (можно включить ручное подтверждение)
        │  concurrency: cd-staging — одно развёртывание за раз
        │  ssh cd-deploy@staging  (ключ → только команда cityduma-deploy)
        ▼
 staging: /opt/cityduma-staging/bin/cityduma-deploy deploy <тег>
   1. тег ∈ {sha-<hex>, X.Y.Z}           — иначе «неверный тег» (2)
   2. все переменные .env заданы         — иначе «нет переменной» (3)
   3. docker pull <образ>:<тег>          — «тега нет в registry» (4) / «registry недоступен» (5)
   4. резервная копия БД (pg_dump)
   5. docker compose up --wait           — миграции, healthcheck всех сервисов
   6. проверка: контейнеры healthy → /health (БД ok) → /version (= тег) → основной сценарий
   7. успех → state/current.tag, история; провал → FAILED + автоматический возврат предыдущей версии
```

На всех шагах 1–3 работающая версия **не трогается**. Выпуск успешен только после шага 6.

## 2. Файлы

| Файл | Назначение |
|---|---|
| [`.github/workflows/cd.yml`](../../.github/workflows/cd.yml) | pipeline доставки: автоматически после CI (main, теги) и вручную (deploy / rollback / verify / status) |
| [`scripts/cd.sh`](../../scripts/cd.sh) | клиент: передаёт конфигурацию окружения и команду на сервер (`make cd-deploy TAG=…`) |
| [`deploy/staging/remote.sh`](../../deploy/staging/remote.sh) | сценарий сервера `cityduma-deploy`: проверки, pull, бэкап, запуск, проверка, возврат, блокировка |
| [`deploy/staging/setup_staging.sh`](../../deploy/staging/setup_staging.sh) | подготовка сервера администратором: Docker, `cd-deploy`, каталоги, `.env`, ключ, iptables |
| [`deploy/staging/staging.env.example`](../../deploy/staging/staging.env.example) | шаблон настроек окружения (без значений) |
| [`scripts/smoke_test.py`](../../scripts/smoke_test.py) | основной пользовательский сценарий после развёртывания |
| [`deploy/staging/demo/Dockerfile`](../../deploy/staging/demo/Dockerfile) | образы «неудачных выпусков» для защиты |
| `GET /version` (`app/main.py`) | версия кода, коммит и время сборки работающего образа |
| `Vagrantfile` → ВМ `staging` (172.27.206.40) | тестовое окружение |

## 3. Выполнение требований

| № | Требование | Реализация |
|---|---|---|
| 1 | Отдельное тестовое окружение | ВМ `staging` (`vagrant up staging`), проект compose `cityduma-staging`, свои volume, порт и пароли |
| 2 | Отдельная учётная запись pipeline | `cd-deploy`: без пароля и sudo, вход только по ключу; в `authorized_keys` — `command="…/cityduma-deploy",restrict`: ключ CI не даёт shell, проброс портов и т.п.; сам сценарий принадлежит root и не может быть изменён этой учётной записью |
| 3 | Образ из registry, без пересборки на сервере | `docker pull` + `compose up --no-build`; на сервере нет исходников, только compose-файл и nginx.conf |
| 4 | Настройки отдельно от образа | `/opt/cityduma-staging/.env` (640 root:cd-deploy) создаёт администратор; pipeline его не меняет и не видит секреты |
| 5 | Автоматическое развёртывание после публикации | `on: workflow_run` CI `completed` + `conclusion == success` (publish выполняется только при зелёном CI) |
| 6 | Ограничение веткой/тегом/подтверждением | только `main` и теги `v*`; environment `staging` с Required reviewers — ручное подтверждение |
| 7 | Проверки после развёртывания | контейнеры healthy и миграции с кодом 0, `/health` с `database=ok`, `/version`, основной сценарий (`smoke_test.py`) |
| 8 | `/version` | `{"version","commit","build_time","environment","instance"}`; commit и время задаются при сборке (`ARG` → `ENV`) |
| 9 | Неуспешная проверка = неуспешный выпуск | код ≠ 0, запись `FAILED` в `state/releases.log`, job CD красный; `current.tag` не меняется |
| 10 | Конкретный тег и ручной возврат | `deploy <тег>`; `rollback` (предыдущая успешная) или `rollback <тег>`; в Actions — Run workflow → action |
| 11 | Нет одновременных конфликтующих развёртываний | `concurrency: cd-staging` в GitHub + `flock` на сервере (второе получает код 75) |
| 12 | Сквозной выпуск функции | раздел 5 |
| 13 | Неудачный выпуск и возврат | раздел 6, сценарии 3–4 и 6 |

## 4. Подготовка окружения (один раз)

```bash
# 1. ключ pipeline (файлы в .gitignore)
ssh-keygen -t ed25519 -N "" -C cd-deploy -f deploy/cd_deploy_key

# 2. ВМ staging: Docker, cd-deploy с принудительной командой, .env со случайными паролями, iptables
vagrant up staging
#   для приватного образа: на ВМ  sudo REGISTRY_USER=<логин> REGISTRY_TOKEN=<PAT read:packages> \
#                                  bash /opt/cityduma-src/deploy/staging/setup_staging.sh

# 3. GitHub → Settings → Environments → New environment «staging»:
#    Secrets:   STAGING_SSH_KEY  = содержимое deploy/cd_deploy_key
#               STAGING_KNOWN_HOSTS = вывод: ssh-keyscan -p 2223 127.0.0.1  (или адрес сервера)
#    Variables: STAGING_HOST, STAGING_PORT, STAGING_URL
#    Required reviewers (по желанию) — ручное подтверждение каждого выпуска
#    Deployment branches and tags: main и v*
```

**Сеть.** ВМ VirtualBox не видна из интернета, поэтому облачный раннер GitHub до неё не достанет.
Варианты: (а) staging на облачной ВМ с публичным адресом — `CD_RUNS_ON` не задавать;
(б) self-hosted runner на компьютере/ВМ в той же сети (Settings → Actions → Runners → New, метки
`self-hosted,staging`) и переменная `CD_RUNS_ON=["self-hosted","staging"]`.
Без GitHub всё то же самое выполняется вручную: `STAGING_HOST=127.0.0.1 STAGING_PORT=2223
STAGING_SSH_KEY=deploy/cd_deploy_key make cd-deploy TAG=sha-<commit>`.

## 5. Сквозной выпуск функции (п. 12)

Функция — адрес `/version` (нужен самой ЛР6 для проверки релиза):

```bash
# задача: Issue «Определение работающей версии» → ветка
git checkout -b feature/version-endpoint develop
# … код app/main.py (/version), Dockerfile (APP_COMMIT, APP_BUILD_TIME), тесты …
make verify && make container-check          # локальные проверки
git push -u origin feature/version-endpoint  # CI на ветке
# PR → develop (ревью, CI зелёный) → release/0.6.0 → PR в main → merge → tag v0.6.0
git tag -a v0.6.0 -m "v0.6.0 — CD и /version" && git push origin main v0.6.0
```

Дальше без участия человека: CI на `main` публикует `sha-<commit>`, на теге — `0.6.0`;
CD выпускает тег на staging и проверяет его. Результат:

```bash
curl -s http://localhost:8180/version   # {"version":"0.6.0","commit":"<commit>",...}
make cd-status                          # текущая/предыдущая версия, история выпусков
```

## 6. Проверка на защите

Обозначения: `cd = STAGING_HOST=127.0.0.1 STAGING_PORT=2223 STAGING_SSH_KEY=deploy/cd_deploy_key ./scripts/cd.sh`
(или Actions → CD (staging) → Run workflow).

| # | Сценарий | Как воспроизвести | Что видно |
|---|---|---|---|
| 1 | Неверный тег | `cd deploy sha-0000000bad` · `cd deploy latest` | «тега нет в registry» (код 4) · «неверный тег … latest запрещён» (код 2); работающая версия не тронута |
| 2 | Нет переменной окружения | на сервере `sudo sed -i 's/^SMOKE_PASSWORD/#&/' /opt/cityduma-staging/.env`, затем `cd deploy <тег>` | «не заданы переменные окружения: SMOKE_PASSWORD» (код 3), развёртывание не начато; вернуть строку |
| 3 | Неуспешный healthcheck | `make cd-demo-images BASE=ghcr.io/daniilkrivencev/devops2026:<рабочий тег>`, `docker push …:sha-de0000000001`, `cd deploy sha-de0000000001` | `compose up --wait`: app1/app2 unhealthy → FAILED → автоматический возврат предыдущей версии |
| 4 | Приложение запущено, основной сценарий не работает | `docker push …:sha-de0000000002`, `cd deploy sha-de0000000002` | контейнеры healthy, `/health` ok, `/version` ok, но smoke: `POST /api/v1/attendance/ … 500` → FAILED → автоматический возврат |
| 5 | Registry недоступен | на сервере временно запретить выход к registry: `sudo iptables -I OUTPUT -p tcp --dport 443 -j REJECT`, `cd deploy <новый тег>`; затем `sudo iptables -D OUTPUT 1` | «registry недоступен … работающая версия не изменена» (код 5) |
| 6 | Возврат предыдущей версии | `cd rollback` или `cd rollback sha-<commit>` | «ручной возврат: A → B», полная проверка, запись в истории |
| — | Одновременные выпуски | два `cd deploy` одновременно | второй: «уже выполняется другое развёртывание» (код 75); в GitHub второй запуск ждёт в очереди |

История на сервере: `make cd-status` →
```
текущая версия: sha-bbbbbbb2222; предыдущая: sha-aaaaaaa1111
  …  sha-de0000000002  FAILED       deploy
  …  sha-bbbbbbb2222   SUCCESS      auto-rollback
  …  sha-bbbbbbb2222   ROLLED_BACK  after sha-de0000000002
```

## 7. Ограничения и решения

- **Миграции при возврате.** Возврат меняет образ, но не откатывает схему БД: миграции должны быть
  обратно совместимыми (добавление столбцов/таблиц). Перед каждым выпуском делается `pg_dump`
  (`/opt/cityduma-staging/backups/pre-<тег>-<время>.dump`, хранятся 10 последних) — при
  несовместимой миграции данные восстанавливаются `pg_restore` вручную.
- **Учётная запись `cd-deploy` входит в группу docker** (без неё не управлять контейнерами), что
  равносильно правам root на этой ВМ. Поэтому ключ ограничен принудительной командой и `restrict`,
  а staging не используется ни для чего другого.
- **Проверочные данные** сценария создаются и удаляются в рамках проверки (`smoke_test.py`).

Все сценарии из раздела 6 прогнаны на локальном стенде (`DEPLOY_TARGET=local`): успешные выпуски,
коды 2/3/4/5/75, автоматический возврат после неуспешного healthcheck и неработающего сценария,
ручной возврат.
