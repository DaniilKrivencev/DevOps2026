#!/usr/bin/env bash
# =============================================================================
# cityduma-deploy — развёртывание на тестовом окружении (staging), ЛР6.
#
# Устанавливается на сервер в /opt/cityduma-staging/bin/cityduma-deploy и
# запускается ТОЛЬКО так (принудительная команда в authorized_keys пользователя
# cd-deploy): ssh cd-deploy@staging "<команда> [аргументы]".
# Ключ pipeline не даёт shell — только команды ниже.
#
#   sync-config        принять docker-compose.yml и nginx/nginx.conf (tar на stdin)
#   deploy <тег>       выпустить тег: проверки → pull → резервная копия БД → запуск → проверка
#   rollback [<тег>]   вернуть предыдущую успешную версию (или указанный тег)
#   verify             проверить работающий релиз
#   status             текущая версия, история, состояние контейнеров
#
# Образ берётся из registry и на сервере НЕ собирается. Настройки окружения —
# в /opt/cityduma-staging/.env (создаёт администратор, права 600), отдельно от образа.
# Одновременные развёртывания исключены блокировкой (flock).
#
# Коды выхода: 0 успех, 1 релиз не прошёл проверку, 2 неверный вызов/тег,
# 3 нет переменных окружения, 4 тега нет в registry, 5 registry недоступен,
# 75 уже идёт другое развёртывание.
# =============================================================================
set -euo pipefail

STAGING_DIR="${STAGING_DIR:-/opt/cityduma-staging}"
ENV_FILE="$STAGING_DIR/.env"
COMPOSE_DIR="$STAGING_DIR/compose"
STATE_DIR="$STAGING_DIR/state"
BACKUP_DIR="$STAGING_DIR/backups"
LOCK_FILE="$STATE_DIR/deploy.lock"
HISTORY="$STATE_DIR/releases.log"
REQUIRED_VARS=(APP_IMAGE POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB APP_AUTH_USERS SMOKE_USER SMOKE_PASSWORD)
TAG_RE='^(sha-[0-9a-f]{7,40}|[0-9]+\.[0-9]+\.[0-9]+)$'
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-cityduma-staging}"

# вызов через ssh с принудительной командой: аргументы в SSH_ORIGINAL_COMMAND
if [ $# -eq 0 ] && [ -n "${SSH_ORIGINAL_COMMAND:-}" ]; then
  read -r -a ARGS <<<"$SSH_ORIGINAL_COMMAND"
  set -- "${ARGS[@]}"
fi
CMD="${1:-status}"
shift || true

mkdir -p "$STATE_DIR" "$BACKUP_DIR" "$COMPOSE_DIR"
log()  { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
die()  { local code=$1; shift; printf '✗ %s\n' "$*" >&2; exit "$code"; }
record() { printf '%s\t%s\t%s\t%s\n' "$(date -Iseconds)" "$1" "$2" "${3:-}" >> "$HISTORY"; }
current_tag() { cat "$STATE_DIR/current.tag" 2>/dev/null || true; }

load_env() {
  [ -f "$ENV_FILE" ] || die 3 "нет файла настроек $ENV_FILE (создаёт администратор по staging.env.example)"
  set -a; . "$ENV_FILE"; set +a
  local missing=()
  for v in "${REQUIRED_VARS[@]}"; do [ -n "${!v:-}" ] || missing+=("$v"); done
  if [ ${#missing[@]} -gt 0 ]; then
    die 3 "не заданы переменные окружения: ${missing[*]} — развёртывание не начато, работающая версия не изменена"
  fi
  HTTP_PORT="${HTTP_PORT:-8080}"
}

dc() { APP_TAG="$TAG" docker compose --env-file "$ENV_FILE" -f "$COMPOSE_DIR/docker-compose.yml" "$@"; }

with_lock() {
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    die 75 "уже выполняется другое развёртывание ($(cat "$STATE_DIR/deploy.owner" 2>/dev/null || echo '?')) — дождитесь завершения"
  fi
  echo "$CMD $* pid=$$ $(date -Iseconds)" > "$STATE_DIR/deploy.owner"
}

pull_image() {
  local ref="$APP_IMAGE:$TAG" out
  log "загрузка образа $ref из registry"
  if out=$(docker pull -q "$ref" 2>&1); then return 0; fi
  echo "$out" >&2
  if grep -qiE 'manifest unknown|not found|does not exist|unauthorized' <<<"$out"; then
    die 4 "тега $TAG нет в registry ($APP_IMAGE) — проверьте тег; работающая версия не изменена"
  fi
  die 5 "registry недоступен: $(tail -1 <<<"$out") — работающая версия не изменена"
}

backup_db() {
  local cid
  cid=$(dc ps -q db 2>/dev/null || true)
  [ -n "$cid" ] || return 0
  local file="$BACKUP_DIR/pre-${TAG}-$(date +%Y%m%d_%H%M%S).dump"
  log "резервная копия БД перед выпуском → $file"
  dc exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$file"
  ls -1t "$BACKUP_DIR"/pre-*.dump 2>/dev/null | tail -n +11 | xargs -r rm -f   # хранить 10 последних
}

verify() {
  local base="http://127.0.0.1:${HTTP_PORT}" svc cid health
  log "проверка 1/4: контейнеры"
  for svc in db app1 app2 nginx; do
    cid=$(dc ps -q "$svc")
    [ -n "$cid" ] || { echo "  ✗ $svc не запущен"; return 1; }
    health=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid")
    [ "$health" = healthy ] || { echo "  ✗ $svc: $health"; return 1; }
  done
  [ "$(docker inspect -f '{{.State.ExitCode}}' "$(dc ps -aq migrate)")" = 0 ] || { echo "  ✗ миграции завершились с ошибкой"; return 1; }
  echo "  ✔ db, app1, app2, nginx — healthy; миграции применены"

  log "проверка 2/4: служебный адрес /health"
  local body
  body=$(curl -fsS --max-time 5 "$base/health") || { echo "  ✗ /health недоступен"; return 1; }
  grep -q '"database":"ok"' <<<"$body" || { echo "  ✗ /health: $body"; return 1; }
  echo "  ✔ $body"

  log "проверка 3/4: версия (/version)"
  body=$(curl -fsS --max-time 5 "$base/version") || { echo "  ✗ /version недоступен"; return 1; }
  local commit version
  commit=$(sed -n 's/.*"commit":"\([^"]*\)".*/\1/p' <<<"$body")
  version=$(sed -n 's/.*"version":"\([^"]*\)".*/\1/p' <<<"$body")
  case "$TAG" in
    sha-*) [[ "$commit" == "${TAG#sha-}"* ]] || { echo "  ✗ работает commit $commit, ожидался $TAG"; return 1; } ;;
    *)     [ "$version" = "$TAG" ] || { echo "  ✗ работает версия $version, ожидалась $TAG"; return 1; } ;;
  esac
  echo "  ✔ $body"

  log "проверка 4/4: основной пользовательский сценарий"
  dc exec -T -e SMOKE_USER="$SMOKE_USER" -e SMOKE_PASSWORD="$SMOKE_PASSWORD" app1 \
    python -m scripts.smoke_test http://nginx:8080 || return 1
}

release() {  # release <тег> <действие>
  TAG="$1"
  local action="$2" prev
  prev=$(current_tag)
  pull_image
  backup_db
  log "запуск $APP_IMAGE:$TAG (было: ${prev:-нет})"
  if ! dc up -d --no-build --remove-orphans --wait --wait-timeout "${WAIT_TIMEOUT:-180}"; then
    echo "  ✗ контейнеры не перешли в состояние healthy"
    dc ps -a; dc logs --tail=20 app1 migrate || true
    return 1
  fi
  if ! verify; then
    return 1
  fi
  echo "$TAG" > "$STATE_DIR/current.tag"
  [ -n "$prev" ] && [ "$prev" != "$TAG" ] && echo "$prev" > "$STATE_DIR/previous.tag"
  record "$TAG" "SUCCESS" "$action"
  log "✔ выпуск $TAG успешен"
}

cmd_deploy() {
  local tag="${1:-}"
  [[ "$tag" =~ $TAG_RE ]] || die 2 "неверный тег '${tag}': ожидается sha-<commit> или X.Y.Z (latest запрещён)"
  load_env
  with_lock "$tag"
  local prev
  prev=$(current_tag)
  if release "$tag" deploy; then return 0; fi
  record "$tag" "FAILED" "deploy"
  echo "✗ выпуск $tag НЕ прошёл проверку — релиз не считается успешным" >&2
  if [ "${AUTO_ROLLBACK:-1}" = 1 ] && [ -n "$prev" ] && [ "$prev" != "$tag" ]; then
    log "автоматический возврат на предыдущую версию $prev"
    if release "$prev" auto-rollback; then
      record "$prev" "ROLLED_BACK" "after $tag"
    else
      record "$prev" "FAILED" "auto-rollback"
      echo "✗ возврат на $prev тоже не прошёл проверку — нужен администратор" >&2
    fi
  fi
  exit 1
}

cmd_rollback() {
  load_env
  local target="${1:-}"
  [ -n "$target" ] || target=$(cat "$STATE_DIR/previous.tag" 2>/dev/null || true)
  [ -n "$target" ] || die 2 "нет предыдущей успешной версии — укажите тег: rollback <тег>"
  [[ "$target" =~ $TAG_RE ]] || die 2 "неверный тег '$target'"
  with_lock "$target"
  log "ручной возврат: $(current_tag) → $target"
  if release "$target" rollback; then return 0; fi
  record "$target" "FAILED" "rollback"
  die 1 "возврат на $target не прошёл проверку"
}

cmd_verify() {
  load_env
  TAG="$(current_tag)"
  [ -n "$TAG" ] || die 2 "на окружении ещё нет выпущенной версии"
  verify || die 1 "работающий релиз $TAG не прошёл проверку"
  echo "✔ релиз $TAG работает"
}

cmd_status() {
  load_env
  TAG="$(current_tag)"
  echo "текущая версия: ${TAG:-нет}; предыдущая: $(cat "$STATE_DIR/previous.tag" 2>/dev/null || echo нет)"
  echo "история (последние 10):"; tail -n 10 "$HISTORY" 2>/dev/null | sed 's/^/  /' || true
  [ -n "$TAG" ] && dc ps --format 'table {{.Service}}\t{{.Image}}\t{{.Status}}'
  curl -fsS --max-time 5 "http://127.0.0.1:${HTTP_PORT}/version" 2>/dev/null && echo || true
}

cmd_sync_config() {
  with_lock sync-config
  local tmp
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' RETURN
  # принимаются только два файла конфигурации — не код и не секреты
  tar -x -C "$tmp" -f - docker-compose.yml nginx/nginx.conf
  [ -s "$tmp/docker-compose.yml" ] && [ -s "$tmp/nginx/nginx.conf" ] || die 2 "в архиве нет docker-compose.yml и nginx/nginx.conf"
  mkdir -p "$COMPOSE_DIR/nginx"
  install -m 644 "$tmp/docker-compose.yml" "$COMPOSE_DIR/docker-compose.yml"
  install -m 644 "$tmp/nginx/nginx.conf" "$COMPOSE_DIR/nginx/nginx.conf"
  log "✔ конфигурация окружения обновлена"
}

case "$CMD" in
  deploy)      cmd_deploy "$@" ;;
  rollback)    cmd_rollback "$@" ;;
  verify)      cmd_verify ;;
  status)      cmd_status ;;
  sync-config) cmd_sync_config ;;
  *) die 2 "неизвестная команда '$CMD' (deploy|rollback|verify|status|sync-config)" ;;
esac
