# Лабораторные работы — навигация

## С чего начать

> Все команды для всех работ по порядку, начиная с установки, — в [ЗАПУСК.md](../ЗАПУСК.md).

1. Открой папку нужной лабораторной ниже → `README.md`. В самом начале — блок **«▶ Как запустить и показать»**,
   в конце — **«❓ Ответы на основные вопросы»**. Между ними — подробности по каждому пункту задания.
2. Все команды выполняются **из корня репозитория** (папка `DevOps2026`).
3. Что понадобится:

| Для чего | Что установить |
|---|---|
| ЛР1, ЛР3 локально | Python 3.12, Git Bash (Windows) или Linux/macOS |
| ЛР2, ВМ для ЛР4/ЛР6 | VirtualBox + Vagrant |
| ЛР4, ЛР5 локально | Docker Desktop (или ВМ: `vagrant up docker`) |
| ЛР5, ЛР6 | аккаунт GitHub, вкладка Actions |

> Самый простой способ получить Linux со всем нужным: `vagrant up docker && vagrant ssh docker`,
> затем `cd /opt/cityduma-src` — там Docker, make, git и Python.

Приложение «Городская Дума» — **один сквозной проект** в корне репозитория: каждая
следующая работа развивает его, а не копирует. Поэтому здесь, в `labs/`, лежат отчёты и
материалы по каждой работе, а сам код, на который они ссылаются, — в корне
(`app/`, `deploy/`, `Dockerfile`, `.github/` …). Все команды выполняются из корня репозитория.

| ЛР | Тема | Отчёт | Главные файлы проекта | Проверка |
|----|------|-------|----------------------|----------|
| 1 | Сквозной проект и Git-процесс | [lab1](lab1/README.md) | `app/`, `alembic/`, `CONTRIBUTING.md`, тег `v0.1.0` | `make run`, `git log --graph` |
| 2 | Развёртывание в Linux без контейнеров | [lab2](lab2/README.md) | `Vagrantfile`, `deploy/*.sh`, `deploy/cityduma.service` | `vagrant up` |
| 3 | Проверки, миграции, резервное копирование | [lab3](lab3/README.md) | `Makefile`, `tests/`, `alembic/versions/`, `scripts/` | `make verify` |
| 4 | Контейнеризация | [lab4](lab4/README.md) | `Dockerfile`, `docker-compose.yml`, `nginx/` | `make container-check` |
| 5 | Continuous Integration | [lab5](lab5/README.md) | `.github/workflows/ci*.yml`, `scripts/ci.sh`, `.github/CODEOWNERS` | вкладка Actions, `make ci` |
| 6 | Continuous Delivery | [lab6](lab6/README.md) | `.github/workflows/cd.yml`, `deploy/staging/`, `scripts/cd.sh` | `make cd-deploy TAG=...` |
| 7 | Управление конфигурацией (Ansible) | [lab7](lab7/README.md) | `infra/ansible/`, `.github/workflows/infra.yml` | `make infra-apply ENV=staging`, `make infra-test` |

Версии по тегам: `git checkout v0.1.0` — состояние ЛР1, `v0.5.0` — ЛР4–5, `v0.6.0` — ЛР6, `v0.7.0` — ЛР7.
