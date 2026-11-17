#!/usr/bin/env bash
# =============================================================================
# deploy_db.sh — развёртывание сервера БД (PostgreSQL), ЛР2.
# Сервер БД: 172.27.206.20. Запуск: sudo -E ./deploy_db.sh (или через Vagrant).
#
# Пароли НЕ хранятся в репозитории: передаются переменными окружения
# (Vagrant берёт их из deploy/secrets.env, который в .gitignore):
#   DB_OWNER_PASS — владелец БД (только миграции при развёртывании)
#   DB_APP_PASS   — пользователь приложения (только DML: SELECT/INSERT/UPDATE/DELETE)
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"

: "${DB_OWNER_PASS:?Задайте DB_OWNER_PASS (см. deploy/secrets.env.example)}"
: "${DB_APP_PASS:?Задайте DB_APP_PASS (см. deploy/secrets.env.example)}"
DB_NAME="${DB_NAME:-city_duma}"
DB_OWNER="${DB_OWNER:-duma_owner}"
DB_APP_USER="${DB_APP_USER:-duma_app}"
APP_SERVER_IP="${APP_SERVER_IP:-172.27.206.10}"

echo "=== 1. SSH: ключи, запрет root, администратор ==="
bash ./harden_ssh.sh

echo "=== 2. Установка PostgreSQL ==="
sudo apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q postgresql postgresql-contrib

PG_CONF=$(ls /etc/postgresql/*/main/postgresql.conf | head -n1)
HBA_CONF=$(ls /etc/postgresql/*/main/pg_hba.conf | head -n1)

echo "=== 3. postgresql.conf: слушать только loopback и внутренний адрес ==="
DB_IP=$(hostname -I | tr ' ' '\n' | grep '^172\.27\.206\.' | head -n1 || true)
LISTEN="${DB_LISTEN:-localhost${DB_IP:+,$DB_IP}}"
sudo sed -i "s/^#*\s*listen_addresses\s*=.*/listen_addresses = '${LISTEN}'/" "$PG_CONF"
sudo sed -i "s/^#*\s*password_encryption\s*=.*/password_encryption = scram-sha-256/" "$PG_CONF"

echo "=== 4. pg_hba.conf: подключение к ${DB_NAME} только с сервера приложения ==="
sudo sed -i '/# cityduma-begin/,/# cityduma-end/d' "$HBA_CONF"
sudo tee -a "$HBA_CONF" >/dev/null <<HBA
# cityduma-begin (управляется deploy/deploy_db.sh)
host    ${DB_NAME}    ${DB_APP_USER}    ${APP_SERVER_IP}/32    scram-sha-256
host    ${DB_NAME}    ${DB_OWNER}       ${APP_SERVER_IP}/32    scram-sha-256
# cityduma-end
HBA
sudo chmod 640 "$HBA_CONF"
sudo systemctl restart postgresql
sudo systemctl enable postgresql >/dev/null

echo "=== 5. БД и пользователи с минимальными правами ==="
# Пароли передаются через переменные psql (-v), а не подставляются в текст SQL-файла на диске.
sudo -u postgres psql -v ON_ERROR_STOP=1 -q \
  -v db="$DB_NAME" -v owner="$DB_OWNER" -v app="$DB_APP_USER" \
  -v owner_pass="$DB_OWNER_PASS" -v app_pass="$DB_APP_PASS" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN', :'owner')
  WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'owner') \gexec
SELECT format('CREATE ROLE %I LOGIN', :'app')
  WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'app') \gexec
ALTER ROLE :"owner" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'owner_pass';
ALTER ROLE :"app"   WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE CONNECTION LIMIT 20 PASSWORD :'app_pass';

SELECT format('CREATE DATABASE %I OWNER %I', :'db', :'owner')
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'db') \gexec
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO :"app";

\c :"db"
-- схема принадлежит владельцу; приложению — только использование, без CREATE
ALTER SCHEMA public OWNER TO :"owner";
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO :"app";
-- права на уже созданные таблицы и на будущие (создаёт владелец при миграциях)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO :"app";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO :"app";
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner" IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app";
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner" IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO :"app";
SQL

echo "=== 6. Межсетевой экран (iptables): 5432 только с ${APP_SERVER_IP} ==="
APP_SERVER_IP="$APP_SERVER_IP" bash ./firewall.sh db

echo "=== Сервер БД готов: $(sudo -u postgres psql -tAc 'select version()' | cut -d, -f1) ==="
