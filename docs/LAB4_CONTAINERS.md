# Лабораторная работа №4: Контейнеризация и автоматическая проверка окружения

## 1. Состав окружения

```
                 хост :8080 (единственный опубликованный порт)
                        │
              ┌─────────▼─────────┐  сеть frontend
              │ nginx (uid 101)   │  балансировка, исключение узла, повтор, лимит запросов
              └────┬─────────┬────┘
          ┌────────▼──┐  ┌───▼───────┐
          │ app1      │  │ app2      │   cityduma:<версия>-<sha>, uid 10001, read-only FS
          └────┬──────┘  └─────┬─────┘
               │  сеть backend (internal: нет выхода наружу и с хоста)
          ┌────▼───────────────▼──┐      ┌─────────────┐
          │ db  PostgreSQL 16     │◄─────│ migrate     │ alembic upgrade head (разовый)
          │ volume cityduma_pg_data│      └─────────────┘
          └───────────────────────┘
```

| Файл | Назначение |
|---|---|
| [`Dockerfile`](../Dockerfile) | двухэтапная сборка, `python:3.12.16-slim-trixie`, пользователь `app` (10001), HEALTHCHECK, STOPSIGNAL |
| [`.dockerignore`](../.dockerignore) | «запретить всё, разрешить нужное»: в контекст попадают только `app/`, `alembic/`, `scripts/`, `requirements.txt` |
| [`docker-compose.yml`](../docker-compose.yml) | db, migrate, app1, app2, nginx; сети, volume, healthcheck, порядок запуска, лимиты |
| [`nginx/nginx.conf`](../nginx/nginx.conf) | upstream из двух экземпляров, `max_fails`, `proxy_next_upstream`, `limit_req` |
| [`scripts/container_policy.py`](../scripts/container_policy.py) | запреты (latest, root, секреты, healthcheck, порты) — `make container-lint` |
| [`scripts/container_check.sh`](../scripts/container_check.sh) | полная проверка — `make container-check` |
| [`deploy/install_docker.sh`](../deploy/install_docker.sh) | Docker Engine на Linux-ВМ (`vagrant up docker`) |

## 2. Быстрый старт

```bash
cp .env.example .env        # задать POSTGRES_PASSWORD и APP_AUTH_USERS
make docker-up              # сборка образа cityduma:<версия>-<sha>, запуск, ожидание healthy
curl http://localhost:8080/health
make container-check        # обязательная проверка перед изменением контейнерного окружения
make docker-down
```

На Linux-ВМ: `vagrant up docker && vagrant ssh docker`, затем `cd /opt/cityduma-src` и те же команды.

## 3. Выполнение требований

| № | Требование | Решение |
|---|---|---|
| 1 | Dockerfile и .dockerignore | `Dockerfile`, `.dockerignore` (deny-all + allowlist) |
| 2 | Воспроизводимая сборка | точная версия базового образа (`3.12.16-slim-trixie`, при необходимости — digest через `--build-arg PYTHON_IMAGE=python@sha256:...`); зависимости с `==`; отдельный слой зависимостей (кэш, пока не изменился `requirements.txt`); узкий контекст сборки; тег образа = версия + SHA коммита (`make` задаёт `APP_TAG`) |
| 3 | Непривилегированный пользователь | `USER 10001:10001`; код принадлежит root и только читается; `read_only: true`, `cap_drop: [ALL]`, `no-new-privileges`; nginx — образ `nginx-unprivileged` (uid 101) |
| 4 | Настройки через переменные окружения | `DATABASE_URL`, `AUTH_USERS`, `LOG_LEVEL` и др. задаются в `docker-compose.yml` из `.env`; в образе только несекретные `APP_ENV`, `PATH` |
| 5 | Корректное завершение по сигналу | exec-форма `CMD` → uvicorn получает SIGTERM (через `init: true`/tini), перестаёт принимать запросы, ждёт текущие до 15 с (`--timeout-graceful-shutdown`), в `lifespan` закрывает пул соединений с БД; `stop_grace_period: 20s` > 15 с |
| 6 | Compose для приложения и БД | `docker-compose.yml` |
| 7 | Внутренняя сеть, volume, healthcheck, порядок запуска | сети `frontend` / `backend (internal)`; volume `pg_data`; healthcheck у db (`pg_isready`), app (`scripts.healthcheck`: `/health` + `database=ok`), nginx; `depends_on`: db healthy → migrate completed → app healthy → nginx |
| 8 | Порт БД не публикуется | у `db` нет `ports`, сеть `backend` — internal; проверяет `container_policy.py` и шаг 5 `container-check` |
| 9 | Сохранность данных | шаг 8 `container-check`: запись переживает `--force-recreate` и обновление образа на новый тег |
| 10 | Миграции, бэкап, восстановление в контейнерах | `make docker-migrate`, `make docker-backup`, `make docker-restore BACKUP=...`, `make docker-restore-new-volume BACKUP=... VOLUME=...` |
| 11 | Ограничения ресурсов | см. раздел 4 |
| 12 | `make container-check` | `scripts/container_check.sh` — 12 проверок на отдельном стенде (`cityduma-check`, свой порт и volume, случайные пароли) |
| 13 | Запреты | раздел 5, проверяются автоматически |
| 14 | Изменения только после `container-check` | зафиксировано в `CONTRIBUTING.md`; в CI (ЛР5) шаг обязателен перед публикацией |

## 4. Ограничения ресурсов и обоснование

| Сервис | CPU | Память | Обоснование |
|---|---|---|---|
| `app1`, `app2` | 0.5 | 256 MiB (резерв 96 MiB), pids 128 | один процесс uvicorn: в покое ~70–90 MiB, под нагрузкой пул SQLAlchemy и запросы — до ~150 MiB; запас ×1.5 до OOM. Приложение I/O-bound (ожидание БД), половины ядра хватает; второй экземпляр даёт горизонтальный запас. `pids` защищает от fork-бомбы |
| `db` | 1.0 | 512 MiB (резерв 128 MiB) | PostgreSQL по умолчанию `shared_buffers=128MB` + рабочая память соединений (2 экземпляра × до 15 соединений); БД — самый нагруженный по CPU компонент. `shm_size: 128m` для параллельных запросов |
| `nginx` | 0.25 | 64 MiB | прокси без кэша и TLS потребляет единицы MiB |
| `migrate` | 0.5 | 256 MiB | тот же образ, что у приложения, работает секунды |

Суммарно ≤ 2.25 CPU и ≈ 1.1 GiB — помещается на ВМ `docker` (2 vCPU, 3 GiB) с запасом для ОС.
Лимиты задаются в `deploy.resources` и применяются `docker compose` без Swarm.

## 5. Запреты (п. 13) и как они проверяются

| Запрещено | Проверка |
|---|---|
| тег `latest` и образы без тега | `container_policy.py`: `FROM` (с подстановкой `ARG`) и все `image:`; образ приложения тегируется версией и SHA |
| запуск от root | `USER` последнего этапа Dockerfile, `user:` в Compose, `privileged`, `network_mode: host`; на стенде — `id -u` в app1/app2/nginx и `Config.User` образа |
| секреты в образе | `ENV`/`ARG`/build-args с именами `*PASSWORD*`, `*SECRET*`, `*TOKEN*`, `AUTH_USERS`…; `.dockerignore` исключает `.env`; на стенде — переменные образа и отсутствие `/app/.env` |
| отключение healthcheck | `HEALTHCHECK NONE`, `disable: true`, `test: [NONE]`; у каждого долгоживущего сервиса healthcheck обязателен |
| публикация лишних портов | разрешён только `nginx:8080` (`ALLOWED_PORTS`); на стенде — `docker port` у app1/app2/db пуст |

`container_policy.py` покрыт unit-тестами (`tests/unit/test_container_policy.py`) и сам является
критическим файлом приёмки (CODEOWNERS).

## 6. Дополнительное задание: Nginx, масштабирование, отказоустойчивость

| № | Пункт | Решение |
|---|---|---|
| 20 | Nginx отдельным контейнером | сервис `nginx` (`nginx-unprivileged:1.31.7-alpine`) |
| 21 | Нет доступа в обход Nginx | у app1/app2 только `expose`, без `ports`; опубликован только 8080 |
| 22 | ≥ 2 экземпляра | `app1`, `app2` (общий шаблон `x-app`) |
| 23 | Распределение запросов | `upstream` round-robin, `keepalive` |
| 24 | Идентификатор экземпляра | заголовок `X-Instance-ID` и поле `instance` в `/health`; nginx добавляет `X-Upstream` |
| 25 | Остановка экземпляра | `docker compose stop app2` → запросы продолжают обслуживаться (шаг 9 `container-check`) |
| 26 | Исключение узла, повтор, лимит | `max_fails=2 fail_timeout=10s`, `proxy_next_upstream error timeout http_502..504`, `limit_req 20r/s burst=40` (ответ 429) |

### Что мешает горизонтальному масштабированию (п. 27)

1. **Единственный экземпляр PostgreSQL** — точка отказа и предел производительности; нужны реплики/кластер.
2. **Пулы соединений**: каждый экземпляр держит свой пул (до 15 соединений), при N экземплярах
   легко упереться в `max_connections` — нужен PgBouncer.
3. **Статический список upstream** в nginx: новый экземпляр требует правки конфигурации и
   `nginx -s reload`; адреса резолвятся при старте nginx (после пересоздания контейнера —
   `docker compose restart nginx`). Нужен service discovery или оркестратор.
4. **Nginx в одном экземпляре** — сам стал точкой отказа; ограничение частоты считается локально.
5. **Миграции** должны выполняться ровно один раз — поэтому вынесены в отдельный сервис `migrate`,
   а не в старт приложения (иначе экземпляры будут мигрировать одновременно).
6. **Резервное копирование** привязано к локальному volume хоста.
7. **Журналы** пишутся в stdout каждого контейнера — для N экземпляров нужен централизованный сбор.
8. Что **не мешает**: авторизация HTTP Basic без серверных сессий, состояние только в БД,
   файлы не сохраняются локально — экземпляры взаимозаменяемы.

## 7. Проверка на защите

```bash
vagrant up docker && vagrant ssh docker
cd /opt/cityduma-src && cp .env.example .env && nano .env

# 15. Собрать и запустить на Linux-ВМ
make docker-up && docker compose ps

# 16. Пользователь процесса
docker compose exec app1 id                    # uid=10001(app)
docker compose top app1                        # UID 10001
docker compose exec nginx id -u                # 101

# 17. Сохранность данных после пересоздания
curl -u admin:<пароль> -X POST localhost:8080/api/v1/deputies/ -H 'Content-Type: application/json' \
     -d '{"full_name":"Проверка Данных Иванович"}'
docker compose down && docker compose up -d --wait
curl -s localhost:8080/api/v1/deputies/        # запись на месте (volume cityduma_pg_data)

# 18. Корректное завершение
time docker compose stop app1                  # секунды, не 20 с
docker compose logs app1 | tail -4             # Graceful shutdown ... Application shutdown complete
docker inspect -f '{{.State.ExitCode}}' cityduma-app1-1   # 143 = SIGTERM обработан (137 было бы SIGKILL)
docker compose start app1

# 19. Восстановление БД в новый volume
make docker-backup                             # backups/pg_<время>.dump
make docker-restore-new-volume BACKUP=backups/pg_<время>.dump VOLUME=cityduma_pg_restored
docker volume ls; curl -s localhost:8080/api/v1/deputies/

# балансировка и отказ экземпляра
for i in $(seq 6); do curl -s -D - -o /dev/null localhost:8080/health | grep -i x-instance; done
docker compose stop app2; curl -s localhost:8080/health; docker compose start app2

# всё сразу
make container-check
```
