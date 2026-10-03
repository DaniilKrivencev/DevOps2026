# -*- mode: ruby -*-
# vi: set ft=ruby :
# =============================================================================
# Vagrantfile — Автоматическое развертывание 2-х ВМ (App + DB) для Лабораторной №2
# Команда запуска для любого разработчика: vagrant up
# =============================================================================

Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/noble64" # Ubuntu 24.04 LTS (без GUI)

  # ─── 1. Сервер Базы Данных (db-server) ──────────────────────────────────────
  config.vm.define "db" do |db|
    db.vm.hostname = "database"
    db.vm.network "private_network", ip: "172.27.206.20"
    db.vm.network "forwarded_port", guest: 22, host: 2220, id: "ssh"

    db.vm.provider "virtualbox" do |vb|
      vb.name = "cityduma-db"
      vb.memory = 2048
      vb.cpus = 2
    end

    # Автоматический провижининг базы данных
    db.vm.provision "shell", path: "deploy/deploy_db.sh"
  end

  # ─── 2. Сервер Приложения (app-server) ──────────────────────────────────────
  config.vm.define "app" do |app|
    app.vm.hostname = "app"
    app.vm.network "private_network", ip: "172.27.206.10"
    app.vm.network "forwarded_port", guest: 22, host: 2221, id: "ssh"
    app.vm.network "forwarded_port", guest: 8000, host: 8000, id: "web"

    app.vm.provider "virtualbox" do |vb|
      vb.name = "cityduma-app"
      vb.memory = 2048
      vb.cpus = 2
    end

    # Копирование исходного кода проекта на ВМ
    app.vm.synced_folder ".", "/opt/cityduma-src"

    # Автоматический провижининг сервера приложений
    app.vm.provision "shell", inline: <<-SHELL
      sudo mkdir -p /opt/cityduma
      sudo cp -r /opt/cityduma-src/app /opt/cityduma-src/alembic /opt/cityduma-src/tests /opt/cityduma-src/requirements.txt /opt/cityduma-src/alembic.ini /opt/cityduma/
      bash /opt/cityduma-src/deploy/deploy_app.sh
    SHELL
  end
end
