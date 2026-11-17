#!/usr/bin/env bash
# =============================================================================
# deploy_app.sh — развёртывание сервера приложения без контейнеров (ЛР2).
# Сервер приложения: 172.27.206.10. Запуск: sudo -E ./deploy_app.sh
#
# Обязательные переменные окружения (секреты не хранятся в репозитории):
#   DB_OWNER_PASS       — владелец БД, используется ТОЛЬКО для миграций, на диск не пишется
#   DB_APP_PASS         — пользователь приложения (DML), записывается в /etc/cityduma/cityduma.env
#   ADMIN_PASSWORD, SECRETARY_PASSWORD — учётные записи приложения (AUTH_USERS)
# Необязательные: SRC_DIR (исходники, по умолчанию корень репозитория), DB_SERVER_IP, APP_PORT.
# Повторный запуск = обновление версии (код, зависимости, миграции, перезапуск).
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"

: "${DB_OWNER_PASS:?Задайте DB_OWNER_PASS}"
: "${DB_APP_PASS:?Задайте DB_APP_PASS}"
: "${ADMIN_PASSWORD:?Задайте ADMIN_PASSWORD}"
: "${SECRETARY_PASSWORD:?Задайте SECRETARY_PASSWORD}"

SRC_DIR="${SRC_DIR:-$(cd .. && pwd)}"
APP_DIR="/opt/cityduma"
CONF_DIR="/etc/cityduma"
APP_USER="duma-app"
APP_PORT="${APP_PORT:-8000}"
DB_SERVER_IP="${DB_SERVER_IP:-172.27.206.20}"
DB_NAME="${DB_NAME:-city_duma}"

urlenc() { python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$1"; }

echo "=== 1. SSH: ключи, запрет root, администратор ==="
bash ./harden_ssh.sh

echo "=== 2. Системные пакеты (среда выполнения Python) ==="
sudo apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q python3 python3-venv python3-pip curl

echo "=== 3. Системный пользователь ${APP_USER} (без shell и домашнего каталога) ==="
if ! id -u "$APP_USER" &>/dev/null; then
    sudo useradd --system --no-create-home --shell /usr/sbin/nologin "$APP_USER"
fi

echo "=== 4. Код приложения в ${APP_DIR} (владелец root, для ${APP_USER} — только чтение) ==="
sudo install -d -m 755 "$APP_DIR"
sudo rm -rf "$APP_DIR/app" "$APP_DIR/alembic"
sudo cp -r "$SRC_DIR/app" "$SRC_DIR/alembic" "$APP_DIR/"
sudo cp "$SRC_DIR/alembic.ini" "$SRC_DIR/requirements.txt" "$APP_DIR/"
sudo find "$APP_DIR" -path "$APP_DIR/venv" -prune -o -name '__pycache__' -prune -exec rm -rf {} +

echo "=== 5. Виртуальное окружение и зафиксированные зависимости (requirements.txt) ==="
[ -d "$APP_DIR/venv" ] || sudo python3 -m venv "$APP_DIR/venv"
sudo "$APP_DIR/venv/bin/pip" install -q --upgrade pip
sudo "$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

# код и venv принадлежат root; приложение читает, но не может изменить себя
sudo chown -R root:"$APP_USER" "$APP_DIR"
sudo find "$APP_DIR" -type d -exec chmod 750 {} +
sudo find "$APP_DIR" -type f -exec chmod 640 {} +
sudo chmod -R 750 "$APP_DIR/venv/bin"

echo "=== 6. Конфигурация ${CONF_DIR}/cityduma.env (640 root:${APP_USER}) ==="
sudo install -d -m 750 -o root -g "$APP_USER" "$CONF_DIR"
sudo install -m 640 -o root -g "$APP_USER" /dev/null "$CONF_DIR/cityduma.env"
sudo tee "$CONF_DIR/cityduma.env" >/dev/null <<ENV
# Создан deploy/deploy_app.sh $(date -Iseconds). Не редактировать вручную без необходимости.
APP_ENV=production
APP_PORT=${APP_PORT}
LOG_LEVEL=INFO
DATABASE_URL=postgresql+asyncpg://duma_app:$(urlenc "$DB_APP_PASS")@${DB_SERVER_IP}:5432/${DB_NAME}
AUTH_USERS=admin:${ADMIN_PASSWORD}:admin,secretary:${SECRETARY_PASSWORD}:secretary
ENV

echo "=== 7. Миграции Alembic от имени владельца БД (пароль не сохраняется) ==="
( cd "$APP_DIR" && sudo -u "$APP_USER" env APP_ENV=production \
    DATABASE_URL="postgresql+asyncpg://duma_owner:$(urlenc "$DB_OWNER_PASS")@${DB_SERVER_IP}:5432/${DB_NAME}" \
    "$APP_DIR/venv/bin/alembic" upgrade head )

echo "=== 8. systemd-служба cityduma ==="
sudo install -m 644 "$SRC_DIR/deploy/cityduma.service" /etc/systemd/system/cityduma.service
sudo systemctl daemon-reload
sudo systemctl enable cityduma >/dev/null
sudo systemctl restart cityduma

echo "=== 9. Межсетевой экран (iptables): SSH и ${APP_PORT} ==="
APP_PORT="$APP_PORT" bash ./firewall.sh app

echo "=== 10. Проверка: служба и /health ==="
for i in $(seq 1 15); do
  if body=$(curl -sf "http://127.0.0.1:${APP_PORT}/health") && echo "$body" | grep -q '"database":"ok"'; then
    echo "/health (попытка $i): $body"
    break
  fi
  if [ "$i" -eq 15 ]; then
    echo "ОШИБКА: /health не ответил с database=ok за 30 секунд: ${body:-нет ответа}" >&2
    sudo journalctl -u cityduma -n 30 --no-pager >&2
    exit 1
  fi
  sleep 2
done
systemctl --no-pager --lines=0 status cityduma
echo "=== Сервер приложения готов: http://$(hostname -I | awk '{print $NF}'):${APP_PORT} ==="
