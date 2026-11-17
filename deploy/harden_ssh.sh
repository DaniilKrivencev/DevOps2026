#!/usr/bin/env bash
# =============================================================================
# harden_ssh.sh — SSH только по ключам, запрет входа root, отдельный администратор.
# Лабораторная работа №2, требования 2–3. Выполняется на ОБЕИХ машинах.
#
#   ADMIN_USER    — имя администратора (по умолчанию duma-admin)
#   ADMIN_PUBKEY  — публичный SSH-ключ администратора (строка ssh-ed25519 ...).
#                   Если не задан — копируются ключи пользователя vagrant,
#                   чтобы не потерять доступ к ВМ.
# Повторный запуск безопасен.
# =============================================================================
set -euo pipefail

ADMIN_USER="${ADMIN_USER:-duma-admin}"

echo "=== SSH: администратор ${ADMIN_USER} (sudo, вход только по ключу) ==="
if ! id -u "$ADMIN_USER" &>/dev/null; then
    sudo useradd --create-home --shell /bin/bash --groups sudo "$ADMIN_USER"
    # пароль заблокирован: войти можно только по ключу, sudo — без пароля
    sudo passwd -l "$ADMIN_USER" >/dev/null
fi
echo "$ADMIN_USER ALL=(ALL) NOPASSWD:ALL" | sudo tee "/etc/sudoers.d/90-${ADMIN_USER}" >/dev/null
sudo chmod 440 "/etc/sudoers.d/90-${ADMIN_USER}"
sudo visudo -cf "/etc/sudoers.d/90-${ADMIN_USER}" >/dev/null

ADMIN_HOME="$(getent passwd "$ADMIN_USER" | cut -d: -f6)"
sudo install -d -m 700 -o "$ADMIN_USER" -g "$ADMIN_USER" "$ADMIN_HOME/.ssh"
AUTH_KEYS="$ADMIN_HOME/.ssh/authorized_keys"
if [ -n "${ADMIN_PUBKEY:-}" ]; then
    echo "$ADMIN_PUBKEY" | sudo tee "$AUTH_KEYS" >/dev/null
elif [ -f /home/vagrant/.ssh/authorized_keys ]; then
    sudo cp /home/vagrant/.ssh/authorized_keys "$AUTH_KEYS"
fi
if [ -f "$AUTH_KEYS" ]; then
    sudo chown "$ADMIN_USER:$ADMIN_USER" "$AUTH_KEYS"
    sudo chmod 600 "$AUTH_KEYS"
fi

echo "=== SSH: запрет root и паролей (drop-in /etc/ssh/sshd_config.d/10-cityduma.conf) ==="
sudo tee /etc/ssh/sshd_config.d/10-cityduma.conf >/dev/null <<'CONF'
# Управляется deploy/harden_ssh.sh (ЛР2)
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
PermitEmptyPasswords no
MaxAuthTries 3
CONF
# в основном конфиге тоже, на случай если drop-in отключены
sudo sed -i 's/^#*\s*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo sed -i 's/^#*\s*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config

# проверка синтаксиса до перезапуска — не потерять доступ из-за опечатки
sudo sshd -t
sudo systemctl restart ssh
echo "SSH: $(sudo sshd -T | grep -E '^(permitrootlogin|passwordauthentication|pubkeyauthentication) ' | tr '\n' ' ')"
