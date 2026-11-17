#!/usr/bin/env bash
# Точка входа управляющего контейнера: готовит ключи и пароль vault, затем
# выполняет переданную команду (ansible-playbook …, ansible-lint …).
set -euo pipefail
mkdir -p ~/.ssh && chmod 700 ~/.ssh
# ключи Vagrant-ВМ (.vagrant/ не в репозитории) — ssh требует права 600
for key in /repo/.vagrant/machines/*/virtualbox/private_key; do
  [ -f "$key" ] || continue
  name=$(basename "$(dirname "$(dirname "$key")")")
  install -m 600 "$key" ~/.ssh/vagrant-"$name".key
done
# ключ стенда «чистой машины» (make infra-test)
if [ -f /repo/infra/ansible/test/.work/ci-target.key ]; then
  install -m 600 /repo/infra/ansible/test/.work/ci-target.key ~/.ssh/ci-target.key
elif [ -f test/.work/ci-target.key ]; then
  install -m 600 test/.work/ci-target.key ~/.ssh/ci-target.key
fi
# ключ для CI / реальных серверов
if [ -n "${ANSIBLE_SSH_KEY:-}" ]; then
  printf '%s\n' "$ANSIBLE_SSH_KEY" > ~/.ssh/ansible.key && chmod 600 ~/.ssh/ansible.key
fi
# пароль vault: переменная CI или локальный файл .vault_pass (в .gitignore)
if [ -n "${ANSIBLE_VAULT_PASSWORD:-}" ]; then
  printf '%s' "$ANSIBLE_VAULT_PASSWORD" > ~/.vault_pass && chmod 600 ~/.vault_pass
  export ANSIBLE_VAULT_PASSWORD_FILE=~/.vault_pass
elif [ -f .vault_pass ]; then
  export ANSIBLE_VAULT_PASSWORD_FILE="$PWD/.vault_pass"
fi
exec "$@"
