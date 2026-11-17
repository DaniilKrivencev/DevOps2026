#!/usr/bin/env bash
# =============================================================================
# install_docker.sh — Docker Engine + Compose plugin на Ubuntu/Debian (ЛР4, ЛР6).
# Официальный репозиторий download.docker.com. Повторный запуск безопасен.
#   DOCKER_USERS="duma-admin vagrant" — кого добавить в группу docker
# =============================================================================
set -euo pipefail
. /etc/os-release

sudo apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q ca-certificates curl gnupg make git
sudo install -m 0755 -d /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/docker.asc ]; then
  sudo curl -fsSL "https://download.docker.com/linux/${ID}/gpg" -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
fi
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${ID} ${VERSION_CODENAME} stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker

for u in ${DOCKER_USERS:-}; do
  id -u "$u" &>/dev/null && sudo usermod -aG docker "$u"
done
docker --version && docker compose version
