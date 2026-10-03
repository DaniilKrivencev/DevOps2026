#!/usr/bin/env bash
# =============================================================================
# deploy_app.sh — Скрипт развертывания сервера приложения (FastAPI + systemd)
# Лабораторная работа №2: Сервер приложения (172.27.206.10)
# =============================================================================

set -e

APP_DIR="/opt/cityduma"
CONF_DIR="/etc/cityduma"
SERVICE_NAME="cityduma"
DB_SERVER_IP="${DB_SERVER_IP:-172.27.206.20}"
DB_PASS="${DB_PASS:-CityDuma2026_SecureDbPass!}"

echo "=== 1. Запрет входа под root по SSH ==="
sudo sed -i 's/#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart ssh

echo "=== 2. Установка системных зависимостей ==="
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv libpq-dev git curl ufw

echo "=== 3. Создание системного пользователя duma-app ==="
if ! id -u duma-app &>/dev/null; then
    sudo useradd --system --no-create-home --shell /usr/sbin/nologin duma-app
fi

echo "=== 4. Настройка каталогов и виртуального окружения ==="
sudo mkdir -p "$APP_DIR"
sudo chown -R "$USER:$USER" "$APP_DIR"

if [ ! -d "$APP_DIR/venv" ]; then
    python3 -m venv "$APP_DIR/venv"
fi

"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install "fastapi>=0.111" "uvicorn[standard]" "sqlalchemy[asyncio]>=2.0" "alembic>=1.13" "asyncpg>=0.29" jinja2 python-multipart python-dotenv pydantic-settings aiofiles httpx pytest pytest-asyncio anyio

echo "=== 5. Создание файла конфигурации $CONF_DIR/cityduma.env ==="
sudo mkdir -p "$CONF_DIR"
sudo tee "$CONF_DIR/cityduma.env" > /dev/null << EOF
APP_ENV=production
DEBUG=false
SECRET_KEY=CityDuma2026_SecretProductionKey_987654321
DATABASE_URL=postgresql+asyncpg://duma_user:${DB_PASS}@${DB_SERVER_IP}:5432/city_duma
EOF

sudo chown -R root:duma-app "$CONF_DIR"
sudo chmod 750 "$CONF_DIR"
sudo chmod 640 "$CONF_DIR/cityduma.env"

sudo chown -R duma-app:duma-app "$APP_DIR"
sudo chmod -R 755 "$APP_DIR"

echo "=== 6. Применение миграций Alembic ==="
sudo env -C "$APP_DIR" --file="$CONF_DIR/cityduma.env" "$APP_DIR/venv/bin/alembic" upgrade head

echo "=== 7. Настройка systemd-службы ==="
sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << EOF
[Unit]
Description=City Duma Management System (FastAPI)
After=network.target

[Service]
Type=simple
User=duma-app
Group=duma-app
WorkingDirectory=$APP_DIR

EnvironmentFile=$CONF_DIR/cityduma.env
ExecStart=$APP_DIR/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2

Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo "=== 8. Настройка UFW Firewall ==="
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 8000/tcp comment 'City Duma Web API'
sudo ufw --force enable
sudo ufw status verbose

echo "=== 9. Проверка статуса службы ==="
sleep 2
sudo systemctl status "$SERVICE_NAME" --no-pager
curl -s http://127.0.0.1:8000/health

echo -e "\n=== Сервер приложения успешно развернут! ==="
