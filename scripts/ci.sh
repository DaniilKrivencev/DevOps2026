#!/usr/bin/env bash
# =============================================================================
# scripts/ci.sh <этап> — этапы CI (ЛР5). Один и тот же сценарий запускается
# в GitHub Actions (Docker-in-Docker) и локально (make ci-<этап>), поэтому
# локальная и серверная проверки совпадают.
#
# Все проверки выполняются в контейнерах:
#   - образ инструментов cityduma-ci:<хэш зависимостей> (Dockerfile, target ci)
#     с примонтированными исходниками запускает те же цели Makefile, что и разработчик;
#   - отдельная тестовая БД — одноразовый контейнер postgres в своей сети.
#
# Этапы:
#   guard      защита файлов приёмки: изменённые критические файлы, запрет удаления тестов
#              (база сравнения — GUARD_BASE: целевая ветка PR / предыдущий коммит ветки)
#   style      make policy, make lint
#   test       make test на отдельной тестовой БД PostgreSQL + make mutation
#   migrations make migrate-check (чистая SQLite) + make migrate-check-pg
#   backup     make restore-demo на PostgreSQL: бэкап → порча данных → восстановление
#   security   make sast, make audit (зависимости), gitleaks (секреты)
#   build      сборка образа приложения → $IMAGE:sha-<sha>, сохранение в reports/image.tar.gz
#   container  make container-check на собранном образе + trivy (уязвимости образа)
#   publish    публикация образа в registry (только после всех проверок)
#   all        все этапы проверки подряд (кроме publish) — локальный аналог pipeline
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

STAGE="${1:?Использование: scripts/ci.sh guard|style|test|migrations|backup|security|build|container|publish|all}"
REPORTS=reports
mkdir -p "$REPORTS"

PG_IMAGE=postgres:16.16-alpine
GITLEAKS_IMAGE=zricethezav/gitleaks:v8.21.2
TRIVY_IMAGE=aquasec/trivy:0.76.2

SHA="${GITHUB_SHA:-$(git rev-parse HEAD 2>/dev/null || echo 0000000000000)}"
SHORT_SHA="${SHA:0:12}"
APP_VERSION="$(sed -n 's/^APP_VERSION = "\(.*\)"/\1/p' app/main.py)"
# образ в registry: ghcr.io/<владелец>/<репозиторий> в нижнем регистре; локально — cityduma
REPO="${GITHUB_REPOSITORY:-local/cityduma}"
IMAGE="${IMAGE:-${REGISTRY:-ghcr.io}/${REPO,,}}"
IMAGE_TAG="sha-${SHORT_SHA}"
RUN_ID="${GITHUB_RUN_ID:-local}-$$"
NET="ci-net-${RUN_ID}"
TESTDB="ci-testdb-${RUN_ID}"

log() { printf '\n\033[0;36m══ [%s] %s\033[0m\n' "$STAGE" "$*"; }

# ─── Образ инструментов (кэш зависимостей) ───────────────────────────────────
DEPS_HASH="$(cat Dockerfile requirements.txt requirements.lock requirements-dev.txt | sha256sum | cut -c1-16)"
TOOLS="cityduma-ci:${DEPS_HASH}"
CACHE_DIR="${CI_CACHE_DIR:-.ci-cache}"

ensure_tools() {
  docker image inspect "$TOOLS" >/dev/null 2>&1 && return
  if [ -f "$CACHE_DIR/tools-${DEPS_HASH}.tar" ]; then
    log "образ инструментов из кэша ($CACHE_DIR)"
    docker load -q -i "$CACHE_DIR/tools-${DEPS_HASH}.tar"
    return
  fi
  log "сборка образа инструментов $TOOLS"
  docker build -q --target ci -t "$TOOLS" . >/dev/null
  if [ -n "${CI:-}" ]; then
    mkdir -p "$CACHE_DIR"
    docker save "$TOOLS" -o "$CACHE_DIR/tools-${DEPS_HASH}.tar"
  fi
}

cleanup() {
  docker rm -f "$TESTDB" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

ensure_net() { docker network inspect "$NET" >/dev/null 2>&1 || docker network create "$NET" >/dev/null; }

# tools <команда> — выполнить команду в контейнере инструментов с исходниками проекта
tools() {
  ensure_tools
  ensure_net
  # передаются только заданные переменные: пустая переменная ≠ отсутствующей
  local envs=() name
  for name in CI TEST_DATABASE_URL PG_URL DATABASE_URL APP_ENV \
              GUARD_ALLOW_TEST_REMOVAL GITHUB_STEP_SUMMARY; do
    [ -n "${!name:-}" ] && envs+=(-e "$name=${!name}")
  done
  docker run --rm --network "$NET" \
    -v "$PWD:$PWD" -w "$PWD" -u "$(id -u):$(id -g)" \
    -e HOME=/tmp "${envs[@]}" \
    "$TOOLS" sh -c "$*"
}

# tmake <цели> — те же цели Makefile, что запускает разработчик (PY=python из образа)
tmake() { tools make PY=python "$@"; }

# start_testdb — отдельная одноразовая тестовая БД PostgreSQL (не рабочая!)
start_testdb() {
  ensure_net
  local pass
  pass="$(od -An -N12 -tx1 /dev/urandom | tr -d ' \n')"
  docker run -d --name "$TESTDB" --network "$NET" --tmpfs /var/lib/postgresql/data \
    -e POSTGRES_USER=ci_test -e POSTGRES_PASSWORD="$pass" -e POSTGRES_DB=city_duma_test \
    "$PG_IMAGE" >/dev/null
  for _ in $(seq 1 30); do
    docker exec "$TESTDB" pg_isready -U ci_test -d city_duma_test -h 127.0.0.1 >/dev/null 2>&1 && break
    sleep 1
  done
  docker exec "$TESTDB" pg_isready -U ci_test -d city_duma_test -h 127.0.0.1 >/dev/null
  export TESTDB_URL="postgresql+asyncpg://ci_test:${pass}@${TESTDB}:5432/city_duma_test"
}

stage_guard() {
  local base="${GUARD_BASE:-origin/develop}"
  log "критические файлы приёмки и удаление тестов (база: $base)"
  # GITHUB_STEP_SUMMARY — файл раннера вне рабочего каталога: пишем отчёт в reports/
  GITHUB_STEP_SUMMARY="$PWD/$REPORTS/guard.md" tools "git config --global --add safe.directory '$PWD' && python -m scripts.acceptance_guard '$base'"
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ] && [ -f "$REPORTS/guard.md" ]; then
    cat "$REPORTS/guard.md" >> "$GITHUB_STEP_SUMMARY"
  fi
}

stage_style() {
  log "стиль и правила проекта: make policy lint"
  tmake policy lint
}

stage_test() {
  start_testdb
  log "тесты на отдельной тестовой БД PostgreSQL ($PG_IMAGE) + покрытие"
  TEST_DATABASE_URL="$TESTDB_URL" tmake test
  log "мутационное тестирование бизнес-правил"
  tmake mutation
}

stage_migrations() {
  log "миграции: чистая БД + alembic check"
  tmake migrate-check
  start_testdb
  log "миграции на PostgreSQL: чистая БД, БД с данными, откат и повторное применение"
  PG_URL="$TESTDB_URL" tmake migrate-check-pg
}

stage_backup() {
  start_testdb
  log "резервное копирование и восстановление на PostgreSQL"
  APP_ENV=development DATABASE_URL="$TESTDB_URL" tmake restore-demo
}

stage_security() {
  log "SAST (bandit)"
  tmake sast
  log "уязвимости зависимостей (pip-audit)"
  tmake audit
  log "поиск секретов в коде и истории (gitleaks)"
  docker run --rm -v "$PWD:$PWD" -w "$PWD" -u "$(id -u):$(id -g)" "$GITLEAKS_IMAGE" \
    git --config .gitleaks.toml --redact --no-banner -v \
    --report-format json --report-path "$REPORTS/gitleaks.json" .
}

stage_build() {
  log "сборка образа $IMAGE:$IMAGE_TAG"
  docker build --target runtime \
    --build-arg APP_VERSION="$APP_VERSION" --build-arg GIT_SHA="$SHA" \
    --build-arg BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    -t "$IMAGE:$IMAGE_TAG" .
  docker save "$IMAGE:$IMAGE_TAG" | gzip -1 > "$REPORTS/image.tar.gz"
  echo "$IMAGE:$IMAGE_TAG" > "$REPORTS/image.txt"
}

load_built_image() {
  if ! docker image inspect "$IMAGE:$IMAGE_TAG" >/dev/null 2>&1; then
    [ -f "$REPORTS/image.tar.gz" ] || stage_build
    docker load -q -i "$REPORTS/image.tar.gz"
  fi
}

stage_container() {
  load_built_image
  log "make container-check на образе $IMAGE:$IMAGE_TAG"
  ensure_tools
  APP_IMAGE="$IMAGE" APP_TAG="$IMAGE_TAG" SKIP_BUILD=1 PY=python3 ./scripts/container_check.sh
  log "уязвимости образа (trivy): CRITICAL с исправлением — ошибка"
  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock "$TRIVY_IMAGE" \
    image --quiet --format table --severity HIGH,CRITICAL "$IMAGE:$IMAGE_TAG" \
    > "$REPORTS/trivy.txt" || true
  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock "$TRIVY_IMAGE" \
    image --quiet --exit-code 1 --ignore-unfixed --severity CRITICAL "$IMAGE:$IMAGE_TAG"
}

stage_publish() {
  : "${REGISTRY_USER:?нет REGISTRY_USER (защищённая переменная CI)}"
  : "${REGISTRY_PASSWORD:?нет REGISTRY_PASSWORD (защищённая переменная CI)}"
  load_built_image
  log "публикация $IMAGE:$IMAGE_TAG"
  echo "$REGISTRY_PASSWORD" | docker login "${IMAGE%%/*}" -u "$REGISTRY_USER" --password-stdin
  docker push "$IMAGE:$IMAGE_TAG"
  # для тега версии vX.Y.Z — дополнительный тег X.Y.Z (latest не используется)
  if [[ "${GITHUB_REF:-}" == refs/tags/v* ]]; then
    local version="${GITHUB_REF#refs/tags/v}"
    docker tag "$IMAGE:$IMAGE_TAG" "$IMAGE:$version"
    docker push "$IMAGE:$version"
  fi
  docker logout "${IMAGE%%/*}" >/dev/null
}

case "$STAGE" in
  guard|style|test|migrations|backup|security|build|container|publish) "stage_$STAGE" ;;
  all)
    for s in guard style test migrations backup security build container; do
      STAGE=$s "stage_$s"
    done
    ;;
  *) echo "неизвестный этап: $STAGE" >&2; exit 2 ;;
esac
printf '\n\033[0;32m✔ этап %s пройден\033[0m\n' "$STAGE"
