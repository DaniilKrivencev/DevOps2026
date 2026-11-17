#!/usr/bin/env bash
# =============================================================================
# scripts/cd.sh — доставка на тестовое окружение (ЛР6), запускается pipeline'ом
# (.github/workflows/cd.yml) или вручную с машины, у которой есть ключ cd-deploy.
#
#   scripts/cd.sh deploy <тег>     конфигурация окружения → выпуск тега → проверка
#   scripts/cd.sh rollback [<тег>] ручной возврат предыдущей (или указанной) версии
#   scripts/cd.sh verify | status
#
# Переменные:
#   STAGING_HOST, STAGING_PORT (22), STAGING_USER (cd-deploy), STAGING_SSH_KEY (путь к ключу)
#   DEPLOY_TARGET=local — выполнить сценарий сервера на этой машине (стенд разработчика)
#   STAGING_DIR — каталог окружения для DEPLOY_TARGET=local
# Коды выхода — как у deploy/staging/remote.sh.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

ACTION="${1:?Использование: scripts/cd.sh deploy <тег> | rollback [<тег>] | verify | status}"
shift

remote() {
  if [ "${DEPLOY_TARGET:-ssh}" = local ]; then
    STAGING_DIR="${STAGING_DIR:?задайте STAGING_DIR}" bash deploy/staging/remote.sh "$@"
  else
    : "${STAGING_HOST:?задайте STAGING_HOST}"
    ssh -i "${STAGING_SSH_KEY:?задайте STAGING_SSH_KEY}" -p "${STAGING_PORT:-22}" \
        -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 \
        "${STAGING_USER:-cd-deploy}@${STAGING_HOST}" "$*"
  fi
}

case "$ACTION" in
  deploy)
    TAG="${1:?укажите тег: sha-<commit> или X.Y.Z}"
    echo "▶ конфигурация окружения (docker-compose.yml, nginx.conf)"
    tar -c -f - docker-compose.yml nginx/nginx.conf | remote sync-config
    echo "▶ выпуск $TAG"
    remote deploy "$TAG"
    ;;
  rollback) remote rollback "${1:-}" ;;
  verify)   remote verify ;;
  status)   remote status ;;
  *) echo "неизвестное действие: $ACTION" >&2; exit 2 ;;
esac
