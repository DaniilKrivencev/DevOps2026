#!/usr/bin/env bash
# =============================================================================
# setup_staging.sh — подготовка тестового окружения (staging) для ЛР6.
# Выполняет АДМИНИСТРАТОР один раз (sudo -E bash deploy/staging/setup_staging.sh).
#
#   CD_PUBKEY       — публичный SSH-ключ pipeline (обязателен для доступа CI)
#   REGISTRY_USER / REGISTRY_TOKEN — чтение образов из приватного registry
#                     (токен только с правом read:packages; необязательно)
#
# Создаёт:
#   - Docker Engine (deploy/install_docker.sh);
#   - пользователя cd-deploy — ОТДЕЛЬНАЯ учётная запись pipeline: без пароля и sudo,
#     вход только по ключу с принудительной командой cityduma-deploy (shell недоступен);
#   - /opt/cityduma-staging: bin/ (root, только чтение), compose/, state/, backups/;
#   - .env из staging.env.example со случайными паролями (если ещё нет);
#   - iptables: SSH и порт nginx.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"
SRC="$(cd ../.. && pwd)"
DIR=/opt/cityduma-staging
USER_CD=cd-deploy
rand() { od -An -N12 -tx1 /dev/urandom | tr -d ' \n'; }

echo "=== 1. Docker Engine ==="
DOCKER_USERS="duma-admin" bash "$SRC/deploy/install_docker.sh"

echo "=== 2. Учётная запись pipeline: ${USER_CD} ==="
if ! id -u "$USER_CD" &>/dev/null; then
  sudo useradd --create-home --shell /bin/bash "$USER_CD"
  sudo passwd -l "$USER_CD" >/dev/null
fi
sudo usermod -aG docker "$USER_CD"

echo "=== 3. Каталоги ${DIR} ==="
sudo install -d -m 755 -o root -g root "$DIR" "$DIR/bin"
sudo install -d -m 750 -o "$USER_CD" -g "$USER_CD" "$DIR/compose" "$DIR/compose/nginx" "$DIR/state" "$DIR/backups"
# сценарий развёртывания принадлежит root: учётная запись pipeline не может его изменить
sudo install -m 755 -o root -g root remote.sh "$DIR/bin/cityduma-deploy"
sudo install -m 644 -o "$USER_CD" -g "$USER_CD" "$SRC/docker-compose.yml" "$DIR/compose/docker-compose.yml"
sudo install -m 644 -o "$USER_CD" -g "$USER_CD" "$SRC/nginx/nginx.conf" "$DIR/compose/nginx/nginx.conf"

echo "=== 4. Настройки окружения ${DIR}/.env (640 root:${USER_CD}) ==="
if [ ! -f "$DIR/.env" ]; then
  db_pass=$(rand); admin_pass=$(rand); sec_pass=$(rand)
  sed -e "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=${db_pass}/" \
      -e "s/^APP_AUTH_USERS=.*/APP_AUTH_USERS=admin:${admin_pass}:admin,secretary:${sec_pass}:secretary/" \
      -e "s/^SMOKE_PASSWORD=.*/SMOKE_PASSWORD=${admin_pass}/" \
      staging.env.example | sudo tee "$DIR/.env" >/dev/null
  echo "  создан .env со случайными паролями (пароль admin: sudo grep APP_AUTH_USERS $DIR/.env)"
fi
sudo chown root:"$USER_CD" "$DIR/.env"
sudo chmod 640 "$DIR/.env"

echo "=== 5. Ключ pipeline: только команда cityduma-deploy ==="
HOME_CD=$(getent passwd "$USER_CD" | cut -d: -f6)
sudo install -d -m 700 -o "$USER_CD" -g "$USER_CD" "$HOME_CD/.ssh"
if [ -n "${CD_PUBKEY:-}" ]; then
  echo "command=\"$DIR/bin/cityduma-deploy\",restrict $CD_PUBKEY" \
    | sudo tee "$HOME_CD/.ssh/authorized_keys" >/dev/null
  sudo chown "$USER_CD:$USER_CD" "$HOME_CD/.ssh/authorized_keys"
  sudo chmod 600 "$HOME_CD/.ssh/authorized_keys"
else
  echo "  ! CD_PUBKEY не задан — pipeline не сможет подключиться (задайте и запустите снова)"
fi

echo "=== 6. Доступ к registry (только чтение) ==="
if [ -n "${REGISTRY_TOKEN:-}" ]; then
  echo "$REGISTRY_TOKEN" | sudo -u "$USER_CD" -H docker login ghcr.io -u "${REGISTRY_USER:?}" --password-stdin
fi

echo "=== 7. Межсетевой экран: SSH и ${HTTP_PORT:-8080} ==="
APP_PORT="${HTTP_PORT:-8080}" bash "$SRC/deploy/firewall.sh" app

echo "=== Staging готов. Проверка: sudo -u ${USER_CD} ${DIR}/bin/cityduma-deploy status ==="
