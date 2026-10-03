#!/usr/bin/env bash
# =============================================================================
# deploy_db.sh — Скрипт развертывания сервера базы данных (PostgreSQL)
# Лабораторная работа №2: Сервер БД (172.27.206.20)
# =============================================================================

set -e

DB_NAME="city_duma"
DB_USER="duma_user"
DB_PASS="${DB_PASS:-CityDuma2026_SecureDbPass!}"
APP_SERVER_IP="172.27.206.10"

echo "=== 1. Запрет входа под root по SSH ==="
sudo sed -i 's/#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart ssh

echo "=== 2. Установка PostgreSQL ==="
sudo apt-get update
sudo apt-get install -y postgresql postgresql-contrib ufw

echo "=== 3. Настройка postgresql.conf (listen_addresses = '*') ==="
PG_CONF=$(ls /etc/postgresql/*/main/postgresql.conf | head -n1)
sudo sed -i "s/#*listen_addresses\s*=.*/listen_addresses = '*'/" "$PG_CONF"

echo "=== 4. Настройка pg_hba.conf (доступ только с App-сервера) ==="
HBA_CONF=$(ls /etc/postgresql/*/main/pg_hba.conf | head -n1)
if ! sudo grep -q "duma_user" "$HBA_CONF"; then
    echo "host    $DB_NAME       $DB_USER       $APP_SERVER_IP/32        scram-sha-256" | sudo tee -a "$HBA_CONF"
fi

sudo systemctl restart postgresql

echo "=== 5. Создание базы данных и пользователя ==="
cat << EOF > /tmp/init_db.sql
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$DB_USER') THEN
    CREATE USER $DB_USER WITH ENCRYPTED PASSWORD '$DB_PASS';
  ELSE
    ALTER USER $DB_USER WITH ENCRYPTED PASSWORD '$DB_PASS';
  END IF;
END
\$\$;

SELECT 'CREATE DATABASE $DB_NAME OWNER $DB_USER'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME')\gexec

REVOKE ALL ON DATABASE $DB_NAME FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE $DB_NAME TO $DB_USER;

\c $DB_NAME
GRANT ALL ON SCHEMA public TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DB_USER;
EOF

sudo -u postgres psql -f /tmp/init_db.sql
rm -f /tmp/init_db.sql

echo "=== 6. Настройка UFW Firewall ==="
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow from $APP_SERVER_IP to any port 5432 proto tcp comment 'PostgreSQL from App Server only'
sudo ufw --force enable
sudo ufw status verbose

echo "=== Сервер базы данных успешно развернут! ==="
