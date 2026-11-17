#!/usr/bin/env bash
# =============================================================================
# make infra-test — проверка инфраструктурного кода на «чистой машине» (ЛР7).
#
#   1. новый контейнер-сервер (systemd + SSH, ничего не настроено);
#   2. запуск 1: подготовка с нуля → приложение отвечает, проверка пройдена;
#   3. запуск 2: повторно — должно быть changed=0 (нет необоснованных изменений);
#   4. ручные изменения: пароль в SSH, лишний порт в iptables, остановленный nginx,
#      права на файл секретов 0644;
#   5. запуск 3: Ansible восстанавливает требуемое состояние (changed>0), проверка пройдена;
#   6. запуск 4: снова changed=0.
# Журналы: reports/infra-test-*.log. Тот же сценарий выполняет pipeline infra.yml.
#
# Переменные: TARGET_IMAGE (готовый образ «чистой машины»), EXTRA_VARS (доп. -e),
#   REGISTRY_USERNAME / REGISTRY_PASSWORD (если образ приложения в приватном registry),
#   PRELOAD_IMAGES (образы, загружаемые в Docker узла вместо registry — для стенда без интернета),
#   KEEP=1 (не удалять контейнер).
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."                     # infra/ansible
REPO="$(cd ../.. && pwd)"
WORK=test/.work
REPORTS="$REPO/reports"
mkdir -p "$WORK" "$REPORTS"
NAME=cityduma-ci-target
PORT=2222

ansible_run() { "$REPO/scripts/infra.sh" "$@"; }
log() { printf '\n\033[0;36m▶ %s\033[0m\n' "$*"; }
fail() { printf '\033[0;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }
changed_count() { grep -oE 'changed=[0-9]+' "$REPORTS/infra-test-$1.log" | awk -F= '{s+=$2} END {print s+0}'; }
target() { docker exec "$NAME" "$@"; }

cleanup() { [ "${KEEP:-0}" = 1 ] || docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

log "1. Чистая машина"
if [ -z "${TARGET_IMAGE:-}" ]; then
  TARGET_IMAGE=cityduma-ansible-target:test
  docker build -q -t "$TARGET_IMAGE" test >/dev/null
fi
docker rm -f "$NAME" >/dev/null 2>&1 || true
# Docker внутри «сервера» хранит образы в /var/lib/docker и /var/lib/containerd:
# это отдельные тома, а не overlay контейнера (overlay поверх overlay не умеет whiteout-файлы)
docker run -d --name "$NAME" --hostname cityduma-ci --privileged --cgroupns=host \
  -v /sys/fs/cgroup:/sys/fs/cgroup:rw -v /var/lib/docker -v /var/lib/containerd \
  --tmpfs /run --tmpfs /run/lock \
  -p "127.0.0.1:${PORT}:22" "$TARGET_IMAGE" >/dev/null
rm -f "$WORK/ci-target.key" "$WORK/ci-target.key.pub"
ssh-keygen -q -t ed25519 -N "" -C ansible-ci -f "$WORK/ci-target.key"
for _ in $(seq 1 30); do target systemctl is-active --quiet ssh 2>/dev/null && break; sleep 1; done
# единственное, что есть на «чистой машине»: пользователь с ключом и sudo (как у облачных образов)
target useradd -m -s /bin/bash ansible
target sh -c 'echo "ansible ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/ansible && chmod 440 /etc/sudoers.d/ansible'
target install -d -m 700 -o ansible -g ansible /home/ansible/.ssh
docker cp "$WORK/ci-target.key.pub" "$NAME:/home/ansible/.ssh/authorized_keys"
target sh -c 'chown ansible:ansible /home/ansible/.ssh/authorized_keys && chmod 600 /home/ansible/.ssh/authorized_keys'
rm -f "$WORK/known_hosts"
# секреты стенда — случайные на каждый запуск, в репозитории их нет
rnd() { od -An -N12 -tx1 /dev/urandom | tr -d ' \n'; }
cat > "$WORK/ci-secrets.yml" <<SECRETS
vault_postgres_password: "$(rnd)"
vault_app_admin_password: "$(rnd)"
vault_app_secretary_password: "$(rnd)"
vault_registry_username: "${REGISTRY_USERNAME:-}"
vault_registry_password: "${REGISTRY_PASSWORD:-}"
vault_admin_ssh_pubkeys: []
vault_deploy_ssh_pubkey: ""
SECRETS
chmod 600 "$WORK/ci-secrets.yml"

run() {  # run <id> <заголовок> [аргументы ansible-playbook]
  local logf="$REPORTS/infra-test-$1.log"
  log "$2"; shift 2
  # shellcheck disable=SC2086
  ansible_run ansible-playbook -i inventories/ci/hosts.yml site.yml -e @test/.work/ci-secrets.yml \
    ${EXTRA_VARS:-} "$@" | tee "$logf"
  [ "${PIPESTATUS[0]}" = 0 ] || fail "запуск завершился с ошибкой ($logf)"
}

if [ -n "${PRELOAD_IMAGES:-}" ]; then
  run 0 "0. Подготовка без приложения (образы загружаются локально)" --skip-tags app,verify
  for img in $PRELOAD_IMAGES; do
    { docker save --platform linux/amd64 "$img" 2>/dev/null || docker save "$img"; } | docker exec -i "$NAME" docker load -q
  done
fi

run 1 "2. Запуск 1: подготовка чистой машины"

run 2 "3. Запуск 2: повторно — изменений быть не должно"
second=$(changed_count 2)
[ "$second" = 0 ] || fail "повторный запуск изменил $second ресурс(ов) — нарушена повторяемость"
printf '  ✔ changed=0\n'

log "4. Ручные изменения на сервере (имитация дрейфа конфигурации)"
target sed -i 's/^PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config.d/10-cityduma.conf
target iptables -I INPUT -p tcp --dport 5432 -j ACCEPT
target sh -c 'docker stop $(docker ps -qf name=cityduma-nginx) >/dev/null'
target chmod 0644 /opt/cityduma/.env
target sh -c 'grep PasswordAuthentication /etc/ssh/sshd_config.d/10-cityduma.conf; iptables -S INPUT | grep 5432; stat -c "%a %n" /opt/cityduma/.env'

run 3c "4а. Режим --check --diff: расхождения видны, но ничего не меняется" --check --diff
[ "$(changed_count 3c)" -gt 0 ] || fail "--check не показал расхождений"
target grep -q '^PasswordAuthentication yes' /etc/ssh/sshd_config.d/10-cityduma.conf || fail "--check изменил сервер"
printf '  ✔ --check: %s расхождений, сервер не изменён\n' "$(changed_count 3c)"

run 3 "5. Запуск 3: восстановление требуемого состояния"
third=$(changed_count 3)
[ "$third" -gt 0 ] || fail "ручные изменения не обнаружены"
target grep -q '^PasswordAuthentication no' /etc/ssh/sshd_config.d/10-cityduma.conf || fail "SSH не восстановлен"
target sh -c '! iptables -S INPUT | grep -q 5432' || fail "лишнее правило iptables осталось"
[ "$(target stat -c %a /opt/cityduma/.env)" = 640 ] || fail "права .env не восстановлены"
[ -n "$(target docker ps -qf name=cityduma-nginx)" ] || fail "nginx не запущен"
printf '  ✔ восстановлено %s ресурс(ов): SSH, iptables, nginx, права .env\n' "$third"

run 4 "6. Запуск 4: снова без изменений"
fourth=$(changed_count 4)
[ "$fourth" = 0 ] || fail "после восстановления повторный запуск изменил $fourth ресурс(ов)"

printf '\n\033[0;32m══════ ✔ infra-test: чистая машина, повторяемость (changed=0), восстановление после ручных изменений ══════\033[0m\n'
