#!/usr/bin/env bash
# =============================================================================
# scripts/infra.sh <команда> — запуск Ansible (ЛР7) в управляющем контейнере
# с зафиксированными версиями (infra/ansible/Dockerfile). Нужен только Docker.
#   scripts/infra.sh ansible-playbook -i inventories/staging/hosts.yml site.yml
# ANSIBLE_LOCAL=1 — использовать установленный Ansible вместо контейнера.
# Пароль vault: infra/ansible/.vault_pass (в .gitignore) или ANSIBLE_VAULT_PASSWORD.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

if [ "${ANSIBLE_LOCAL:-0}" = 1 ]; then
  cd infra/ansible && exec ./run.sh "$@"
fi
HASH=$(cat infra/ansible/Dockerfile infra/ansible/requirements.txt | sha256sum | cut -c1-12)
IMAGE="cityduma-ansible:${HASH}"
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "▶ сборка управляющего контейнера $IMAGE" >&2
  docker build -q -t "$IMAGE" infra/ansible >/dev/null
fi
tty=()
[ -t 0 ] && [ -t 1 ] && tty=(-it)
exec docker run --rm "${tty[@]}" --network host -v "$PWD:/repo" \
  -e ANSIBLE_VAULT_PASSWORD -e ANSIBLE_SSH_KEY \
  "$IMAGE" "$@"
