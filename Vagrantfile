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

DB_IP     = "172.27.206.20"
APP_IP    = "172.27.206.10"
DOCKER_IP = "172.27.206.30"
STAGING_IP = "172.27.206.40"

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

  # ─── ЛР4: ВМ с Docker для контейнерного окружения ─────────────────────────
  # Не стартует по умолчанию: vagrant up docker
  config.vm.define "docker", autostart: false do |d|
    d.vm.hostname = "cityduma-docker"
    d.vm.network "private_network", ip: DOCKER_IP
    d.vm.network "forwarded_port", guest: 22, host: 2222, id: "ssh"
    d.vm.network "forwarded_port", guest: 8080, host: 8080, id: "nginx"
    d.vm.provider "virtualbox" do |vb|
      vb.name = "cityduma-docker"
      vb.memory = 3072
      vb.cpus = 2
    end
    d.vm.provision "shell",
      inline: "bash /opt/cityduma-src/deploy/harden_ssh.sh && " \
              "DOCKER_USERS='duma-admin vagrant' bash /opt/cityduma-src/deploy/install_docker.sh",
      env: ADMIN_ENV
  end

  # ─── ЛР6: тестовое окружение (staging) для CD ─────────────────────────────
  # vagrant up staging. Ключ pipeline: ssh-keygen -t ed25519 -N "" -f deploy/cd_deploy_key
  # (файлы в .gitignore); публичная часть попадает в authorized_keys cd-deploy.
  config.vm.define "staging", autostart: false do |st|
    st.vm.hostname = "cityduma-staging"
    st.vm.network "private_network", ip: STAGING_IP
    st.vm.network "forwarded_port", guest: 22, host: 2223, id: "ssh"
    st.vm.network "forwarded_port", guest: 8080, host: 8180, id: "nginx"
    st.vm.provider "virtualbox" do |vb|
      vb.name = "cityduma-staging"
      vb.memory = 3072
      vb.cpus = 2
    end
    cd_key = File.join(__dir__, "deploy", "cd_deploy_key.pub")
    cd_env = File.exist?(cd_key) ? { "CD_PUBKEY" => File.read(cd_key).strip } : {}
    st.vm.provision "shell",
      inline: "bash /opt/cityduma-src/deploy/harden_ssh.sh && " \
              "bash /opt/cityduma-src/deploy/staging/setup_staging.sh",
      env: ADMIN_ENV.merge(cd_env)
  end

  # ─── ЛР7: две ЧИСТЫЕ ВМ — окружения staging и production для Ansible ──────
  # Никакого провижининга: всё настраивает infra/ansible (make infra-apply ENV=…).
  # vagrant up infra-stage infra-prod
  {
    "infra-stage" => ["172.27.206.60", 2224, 8280],
    "infra-prod"  => ["172.27.206.70", 2225, 8380],
  }.each do |name, (ip, ssh_port, http_port)|
    config.vm.define name, autostart: false do |m|
      m.vm.hostname = name
      m.vm.synced_folder ".", "/opt/cityduma-src", disabled: true
      m.vm.network "private_network", ip: ip
      m.vm.network "forwarded_port", guest: 22, host: ssh_port, id: "ssh"
      m.vm.network "forwarded_port", guest: 8080, host: http_port, id: "nginx"
      m.vm.provider "virtualbox" do |vb|
        vb.name = "cityduma-#{name}"
        vb.memory = 2048
        vb.cpus = 2
      end
    end
  end
end
