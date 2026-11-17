# -*- mode: ruby -*-
# vi: set ft=ruby :
# =============================================================================
# Vagrantfile — две ВМ без GUI (Ubuntu 24.04 LTS, Debian-подобная) для ЛР2:
#   db  — 172.27.206.20, PostgreSQL
#   app — 172.27.206.10, приложение как systemd-служба (без контейнеров)
# Запуск: vagrant up   (сначала db, затем app)
#
# Секреты: при первом запуске генерируется deploy/secrets.env со случайными
# паролями (файл в .gitignore). Публичный ключ администратора берётся из
# ~/.ssh/id_ed25519.pub или ~/.ssh/id_rsa.pub хоста, если он есть.
# =============================================================================
require "securerandom"

SECRETS_FILE = File.join(__dir__, "deploy", "secrets.env")
unless File.exist?(SECRETS_FILE)
  File.write(SECRETS_FILE, <<~ENV)
    # Сгенерировано Vagrantfile #{Time.now}. НЕ коммитить (файл в .gitignore).
    DB_OWNER_PASS=#{SecureRandom.hex(16)}
    DB_APP_PASS=#{SecureRandom.hex(16)}
    ADMIN_PASSWORD=#{SecureRandom.hex(8)}
    SECRETARY_PASSWORD=#{SecureRandom.hex(8)}
  ENV
  File.chmod(0600, SECRETS_FILE)
end
SECRETS = File.readlines(SECRETS_FILE)
               .map(&:strip)
               .reject { |l| l.empty? || l.start_with?("#") }
               .to_h { |l| l.split("=", 2) }

pubkey_file = ["id_ed25519.pub", "id_rsa.pub"]
                .map { |f| File.join(Dir.home, ".ssh", f) }
                .find { |f| File.exist?(f) }
ADMIN_ENV = pubkey_file ? { "ADMIN_PUBKEY" => File.read(pubkey_file).strip } : {}

DB_IP  = "172.27.206.20"
APP_IP = "172.27.206.10"

Vagrant.configure("2") do |config|
  config.vm.box = "bento/ubuntu-24.04"
  config.vm.synced_folder ".", "/vagrant", disabled: true
  config.vm.synced_folder ".", "/opt/cityduma-src"

  # ─── Сервер базы данных ────────────────────────────────────────────────────
  config.vm.define "db" do |db|
    db.vm.hostname = "cityduma-db"
    # постоянный (статический) адрес во внутренней сети
    db.vm.network "private_network", ip: DB_IP
    db.vm.network "forwarded_port", guest: 22, host: 2220, id: "ssh"
    db.vm.provider "virtualbox" do |vb|
      vb.name = "cityduma-db"
      vb.memory = 1024
      vb.cpus = 1
    end
    db.vm.provision "shell",
      inline: "bash /opt/cityduma-src/deploy/deploy_db.sh",
      env: SECRETS.slice("DB_OWNER_PASS", "DB_APP_PASS")
                  .merge(ADMIN_ENV, "APP_SERVER_IP" => APP_IP)
  end

  # ─── Сервер приложения ─────────────────────────────────────────────────────
  config.vm.define "app" do |app|
    app.vm.hostname = "cityduma-app"
    app.vm.network "private_network", ip: APP_IP
    app.vm.network "forwarded_port", guest: 22, host: 2221, id: "ssh"
    app.vm.network "forwarded_port", guest: 8000, host: 8000, id: "web"
    app.vm.provider "virtualbox" do |vb|
      vb.name = "cityduma-app"
      vb.memory = 1024
      vb.cpus = 1
    end
    app.vm.provision "shell",
      inline: "bash /opt/cityduma-src/deploy/deploy_app.sh",
      env: SECRETS.merge(ADMIN_ENV, "DB_SERVER_IP" => DB_IP,
                         "SRC_DIR" => "/opt/cityduma-src")
  end
end
