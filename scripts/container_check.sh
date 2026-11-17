#!/usr/bin/env bash
# =============================================================================
# make container-check — автоматическая проверка контейнерного окружения (ЛР4).
#
# Поднимает ОТДЕЛЬНЫЙ стенд (проект cityduma-check, свой volume и порт,
# случайные пароли — рабочее окружение разработчика не затрагивается) и проверяет:
#   1. запреты (latest, root, секреты, healthcheck, порты)    — container_policy.py
#   2. образ: пользователь не root, нет секретов и .env в образе
#   3. запуск с healthcheck и порядком старта (compose up --wait)
#   4. процессы приложения и nginx работают не от root
#   5. доступ только через nginx: порты app и db не опубликованы
#   6. миграции в контейнере (alembic current = head)
#   7. балансировка между двумя экземплярами (X-Instance-ID)
#   8. сохранность данных после пересоздания контейнеров и обновления образа
#   9. отказ одного экземпляра — сервис доступен
#  10. корректное завершение по SIGTERM (код 0, а не SIGKILL)
#  11. резервная копия → удаление данных → восстановление
#  12. восстановление БД в НОВЫЙ volume
# Изменения контейнерного окружения принимаются только после успешного запуска.
#
#   scripts/container_check.sh          — всё
#   scripts/container_check.sh lint     — только шаг 1 (быстро, без запуска)
#   KEEP=1 scripts/container_check.sh   — не удалять стенд после проверки
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

MODE="${1:-full}"
REPORTS=reports
mkdir -p "$REPORTS"

PY="${PY:-python3}"
GIT_SHA="${GIT_SHA:-$(git rev-parse --short=12 HEAD 2>/dev/null || echo nogit)}"
APP_VERSION="${APP_VERSION:-$(sed -n 's/^APP_VERSION = "\(.*\)"/\1/p' app/main.py)}"
rand() { od -An -N12 -tx1 /dev/urandom | tr -d ' \n'; }

export COMPOSE_PROJECT_NAME="${CHECK_PROJECT:-cityduma-check}"
export HTTP_PORT="${CHECK_HTTP_PORT:-18080}"
export PG_VOLUME="${COMPOSE_PROJECT_NAME}_pg_data"
export APP_IMAGE="${APP_IMAGE:-cityduma}"
export APP_TAG="${APP_TAG:-${APP_VERSION}-${GIT_SHA}}"
export APP_VERSION GIT_SHA
export POSTGRES_USER=duma_check POSTGRES_DB=city_duma_check
export POSTGRES_PASSWORD="${CHECK_DB_PASSWORD:-$(rand)}"
ADMIN_PASS="$(rand)"
export APP_AUTH_USERS="admin:${ADMIN_PASS}:admin"

# --env-file /dev/null: личный .env разработчика не влияет на проверку
dc() { docker compose --env-file /dev/null "$@"; }
BASE="http://127.0.0.1:${HTTP_PORT}"
STEP=0
step() { STEP=$((STEP + 1)); printf '\n\033[0;36m▶ %s. %s\033[0m\n' "$STEP" "$*"; }
ok()   { printf '  \033[0;32m✔ %s\033[0m\n' "$*"; }
fail() { printf '  \033[0;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# ─── 1. Запреты (статическая проверка) ───────────────────────────────────────
step "Запреты: latest, root, секреты в образе, отключённый healthcheck, лишние порты"
dc config -q
dc config --format json > "$REPORTS/compose.json"
$PY -m scripts.container_policy "$REPORTS/compose.json"
[ "$MODE" = "lint" ] && exit 0

cleanup() {
  if [ "${KEEP:-0}" = "1" ]; then
    echo "KEEP=1: стенд оставлен (docker compose -p $COMPOSE_PROJECT_NAME ...)"
    return
  fi
  dc logs --no-color > "$REPORTS/container-check.log" 2>&1 || true
  dc down -v --remove-orphans >/dev/null 2>&1 || true
  docker volume rm -f "${PG_VOLUME}_restored" >/dev/null 2>&1 || true
}
trap cleanup EXIT

api() { # api METHOD PATH [JSON] → тело ответа; код ответа в $REPORTS/.code
  local method=$1 path=$2 data=${3:-}
  curl -sS -o "$REPORTS/.body" -w '%{http_code}' -u "admin:${ADMIN_PASS}" -X "$method" \
       -H 'Content-Type: application/json' ${data:+-d "$data"} "$BASE$path" > "$REPORTS/.code"
  cat "$REPORTS/.body"
}
code() { cat "$REPORTS/.code"; }
instance() { curl -sS -D - -o /dev/null "$BASE/health" | tr -d '\r' | awk -F': ' 'tolower($1)=="x-instance-id"{print $2}'; }

# ─── 2. Сборка образа ────────────────────────────────────────────────────────
step "Сборка образа ${APP_IMAGE}:${APP_TAG}"
dc build --pull=false app1 >/dev/null 2>&1 || { dc build --pull=false app1; fail "сборка образа"; }
IMAGE="${APP_IMAGE}:${APP_TAG}"
img_user=$(docker image inspect -f '{{.Config.User}}' "$IMAGE")
case "${img_user%%:*}" in ""|root|0) fail "образ запускается от root (User='$img_user')";; esac
ok "USER образа: $img_user"
if docker image inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$IMAGE" \
     | cut -d= -f1 | grep -Eiq 'PASSW|SECRET|TOKEN|PRIVATE|API_?KEY|AUTH_USERS'; then
  fail "в переменных окружения образа есть секреты"
fi
docker run --rm --entrypoint sh "$IMAGE" -c 'test ! -e /app/.env && test ! -e /app/deploy/secrets.env' \
  || fail "в образ попал .env / секреты"
ok "в образе нет .env и переменных с секретами"

# ─── 3. Запуск ───────────────────────────────────────────────────────────────
step "Запуск: db → migrate → app1, app2 → nginx (healthcheck, порядок старта)"
dc up -d --wait --wait-timeout 180 >/dev/null 2>&1 || { dc ps -a; dc logs --tail=30; fail "окружение не поднялось"; }
dc ps --format 'table {{.Service}}\t{{.Status}}'
health=$(curl -fsS "$BASE/health") || fail "/health через nginx недоступен"
grep -q '"database":"ok"' <<<"$health" || fail "/health: $health"
ok "через nginx: $health"

# ─── 4. Пользователь процессов ───────────────────────────────────────────────
step "Процессы работают не от root"
for svc in app1 app2 nginx; do
  uid=$(dc exec -T "$svc" id -u | tr -d '\r')
  [ "$uid" != "0" ] || fail "$svc работает от root"
  ok "$svc: uid=$uid"
done
dc top app1 | sed -n '1,3p'

# ─── 5. Опубликованные порты ─────────────────────────────────────────────────
step "Доступ только через nginx: порты app1/app2/db не опубликованы"
for svc in app1 app2 db; do
  [ -z "$(docker port "$(dc ps -q "$svc")")" ] || fail "$svc публикует порт на хост"
done
ok "опубликован только nginx:${HTTP_PORT}"

# ─── 6. Миграции ─────────────────────────────────────────────────────────────
step "Миграции в контейнере"
current=$(dc run --rm --no-deps migrate alembic current 2>/dev/null)
echo "  $current"
grep -q "(head)" <<<"$current" || fail "БД не на последней ревизии"
dc run --rm --no-deps migrate alembic upgrade head >/dev/null 2>&1 || fail "повторный upgrade head упал"
ok "alembic current = head, повторное применение идемпотентно"

# ─── 7. Балансировка ─────────────────────────────────────────────────────────
step "Балансировка: запросы распределяются между экземплярами"
seen=$(for _ in $(seq 1 10); do instance; done | sort | uniq -c)
echo "$seen"
[ "$(echo "$seen" | wc -l)" -ge 2 ] || fail "ответы только от одного экземпляра"
ok "ответили оба экземпляра"

# ─── 8. Сохранность данных ───────────────────────────────────────────────────
step "Сохранность данных после пересоздания контейнеров и обновления образа"
dep=$(api POST /api/v1/deputies/ '{"full_name":"Проверочный Депутат Контейнеров"}')
[ "$(code)" = 201 ] || fail "создание депутата: $(code) $dep"
DEP_ID=$(echo "$dep" | $PY -c 'import json,sys; print(json.load(sys.stdin)["id"])')
dc up -d --force-recreate --wait --wait-timeout 180 >/dev/null 2>&1
api GET "/api/v1/deputies/$DEP_ID" >/dev/null
[ "$(code)" = 200 ] || fail "после --force-recreate депутат $DEP_ID пропал"
ok "после пересоздания контейнеров запись $DEP_ID на месте"
APP_TAG="${APP_TAG}-upd" dc build --pull=false app1 >/dev/null 2>&1 || { dc build --pull=false app1; fail "сборка образа"; }
APP_TAG="${APP_TAG}-upd" dc up -d --wait --wait-timeout 180 >/dev/null 2>&1
running=$(docker inspect -f '{{.Config.Image}}' "$(dc ps -q app1)")
[ "$running" = "${APP_IMAGE}:${APP_TAG}-upd" ] || fail "образ не обновился: $running"
api GET "/api/v1/deputies/$DEP_ID" >/dev/null
[ "$(code)" = 200 ] || fail "после обновления образа запись пропала"
ok "после обновления образа ($running) запись на месте"
dc up -d --wait --wait-timeout 180 >/dev/null 2>&1   # вернуть исходный тег

# ─── 9. Отказ экземпляра ─────────────────────────────────────────────────────
step "Отказ одного экземпляра: сервис доступен"
dc stop app2 >/dev/null 2>&1
for i in $(seq 1 8); do
  c=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/v1/deputies/")
  [ "$c" = 200 ] || fail "запрос $i при остановленном app2: HTTP $c"
done
ok "app2 остановлен — 8/8 запросов успешны (nginx исключил узел)"
dc start app2 >/dev/null 2>&1
dc up -d --wait --wait-timeout 120 >/dev/null 2>&1

# ─── 10. Корректное завершение ───────────────────────────────────────────────
step "Корректное завершение по SIGTERM"
cid=$(dc ps -q app1)
start=$(date +%s)
dc stop -t 20 app1 >/dev/null 2>&1
took=$(( $(date +%s) - start ))
exit_code=$(docker inspect -f '{{.State.ExitCode}}' "$cid")
logs=$(docker logs "$cid" 2>&1)
grep -q "Graceful shutdown" <<<"$logs" || fail "в журнале нет записи о корректном завершении"
# uvicorn после корректного завершения повторно поднимает полученный сигнал:
# 143 = 128+SIGTERM (завершился сам), 137 = 128+SIGKILL (убит по таймауту) — ошибка
case "$exit_code" in 0|143) ;; *) fail "код завершения $exit_code (137 = убит SIGKILL по таймауту)";; esac
[ "$took" -lt 20 ] || fail "остановка заняла ${took} с — упёрлись в stop_grace_period"
ok "app1 остановлен за ${took} с по SIGTERM (код $exit_code, не SIGKILL), соединения с БД закрыты"
dc start app1 >/dev/null 2>&1
dc up -d --wait --wait-timeout 120 >/dev/null 2>&1

# ─── 11. Резервная копия и восстановление ────────────────────────────────────
step "Резервная копия → удаление данных → восстановление"
DUMP="$REPORTS/container-check.dump"
dc exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$DUMP"
[ -s "$DUMP" ] || fail "пустая резервная копия"
api DELETE "/api/v1/deputies/$DEP_ID" >/dev/null
api GET "/api/v1/deputies/$DEP_ID" >/dev/null
[ "$(code)" = 404 ] || fail "данные не удалились"
dc exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists < "$DUMP"
api GET "/api/v1/deputies/$DEP_ID" >/dev/null
[ "$(code)" = 200 ] || fail "после восстановления записи нет"
ok "запись $DEP_ID восстановлена из $(du -h "$DUMP" | cut -f1) резервной копии"

# ─── 12. Восстановление в новый volume ───────────────────────────────────────
step "Восстановление БД в новый volume"
dc down >/dev/null 2>&1
export PG_VOLUME="${PG_VOLUME}_restored"
dc up -d --wait --wait-timeout 120 db >/dev/null 2>&1
dc exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner < "$DUMP"
dc up -d --wait --wait-timeout 180 >/dev/null 2>&1
vol=$(docker inspect -f '{{range .Mounts}}{{.Name}}{{end}}' "$(dc ps -q db)")
api GET "/api/v1/deputies/$DEP_ID" >/dev/null
[ "$(code)" = 200 ] || fail "в новом volume нет восстановленных данных"
ok "данные восстановлены в новый volume $vol"
dc down -v >/dev/null 2>&1
export PG_VOLUME="${PG_VOLUME%_restored}"

printf '\n\033[0;32m══════ ✔ make container-check: все %s проверок пройдены ══════\033[0m\n' "$STEP"
