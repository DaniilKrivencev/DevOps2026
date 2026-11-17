#!/usr/bin/env bash
# =============================================================================
# firewall.sh — межсетевой экран на iptables (ЛР2, требование 10).
#
#   ./firewall.sh app   — сервер приложения: SSH + порт приложения для клиентов
#   ./firewall.sh db    — сервер БД: SSH + 5432 ТОЛЬКО с сервера приложения
#
# Политика по умолчанию для входящих — DROP; разрешены loopback, ответы на
# установленные соединения, ICMP echo (диагностика), SSH и порт роли.
# Правила сохраняются через netfilter-persistent и переживают перезагрузку.
# =============================================================================
set -euo pipefail

ROLE="${1:?Использование: firewall.sh app|db}"
APP_PORT="${APP_PORT:-8000}"
APP_SERVER_IP="${APP_SERVER_IP:-172.27.206.10}"
SSH_PORT="${SSH_PORT:-22}"

echo "=== iptables: установка iptables-persistent ==="
# ufw не используется: правила задаются напрямую iptables
if command -v ufw >/dev/null; then sudo ufw --force disable >/dev/null || true; fi
echo iptables-persistent iptables-persistent/autosave_v4 boolean false | sudo debconf-set-selections
echo iptables-persistent iptables-persistent/autosave_v6 boolean false | sudo debconf-set-selections
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q iptables iptables-persistent >/dev/null

echo "=== iptables: правила для роли '${ROLE}' ==="
ipt() { sudo iptables "$@"; }

# сначала разрешающая политика, чтобы не оборвать текущую SSH-сессию при сбросе
ipt -P INPUT ACCEPT
ipt -F INPUT
ipt -A INPUT -i lo -j ACCEPT
ipt -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
ipt -A INPUT -m conntrack --ctstate INVALID -j DROP
ipt -A INPUT -p icmp --icmp-type echo-request -j ACCEPT
ipt -A INPUT -p tcp --dport "$SSH_PORT" -m conntrack --ctstate NEW -j ACCEPT -m comment --comment "SSH"

case "$ROLE" in
  app)
    ipt -A INPUT -p tcp --dport "$APP_PORT" -m conntrack --ctstate NEW -j ACCEPT \
        -m comment --comment "City Duma: clients"
    ;;
  db)
    ipt -A INPUT -p tcp -s "$APP_SERVER_IP" --dport 5432 -m conntrack --ctstate NEW -j ACCEPT \
        -m comment --comment "PostgreSQL: app server only"
    # явный отказ с журналированием для всех остальных попыток подключения к БД
    ipt -A INPUT -p tcp --dport 5432 -j LOG --log-prefix "DB-DENY " --log-level 4
    ;;
  *) echo "Неизвестная роль: $ROLE" >&2; exit 1 ;;
esac

ipt -P INPUT DROP
ipt -P FORWARD DROP
ipt -P OUTPUT ACCEPT

# IPv6: всё входящее, кроме loopback и ответов, запрещено
sudo ip6tables -P INPUT ACCEPT
sudo ip6tables -F INPUT
sudo ip6tables -A INPUT -i lo -j ACCEPT
sudo ip6tables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
sudo ip6tables -A INPUT -p ipv6-icmp -j ACCEPT
sudo ip6tables -P INPUT DROP
sudo ip6tables -P FORWARD DROP

sudo netfilter-persistent save >/dev/null
sudo systemctl enable netfilter-persistent >/dev/null 2>&1
sudo iptables -L INPUT -n -v --line-numbers
