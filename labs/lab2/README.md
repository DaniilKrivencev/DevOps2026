# Лабораторная работа №2: Развёртывание приложения в Linux-среде

> ## ▶ Как запустить и показать
>
> Нужны **VirtualBox** и **Vagrant**. Из корня репозитория:
> ```bash
> vagrant up                    # 5–10 мин: создаются ВМ db и app, всё настраивается скриптами
> curl http://localhost:8000/health        # {"status":"ok","database":"ok",...}
> vagrant ssh app               # зайти на сервер приложения (vagrant ssh db — на сервер БД)
> ```
> Пароли сгенерированы в `deploy/secrets.env` (его нет в Git). Вход в веб-интерфейс —
> `admin` / `ADMIN_PASSWORD` оттуда же. Остановить: `vagrant halt`, удалить: `vagrant destroy -f`.
>
> Главное на защите — раздел **5. Проверка на защите** ниже (готовые команды на каждый пункт).

Приложение «Городская Дума» развёрнуто **без контейнеров** на двух Linux-машинах
без графического интерфейса (Ubuntu Server 24.04 LTS — Debian-подобная ОС):

| Машина | Адрес (статический) | Назначение |
|---|---|---|
| `cityduma-app` | `172.27.206.10/24` | приложение (Python 3 + venv, systemd-служба `cityduma`) |
| `cityduma-db`  | `172.27.206.20/24` | PostgreSQL 16 |

Всё развёртывание воспроизводится одной командой `vagrant up` или скриптами
из каталога [`deploy/`](../../deploy) на любых двух чистых Debian/Ubuntu-машинах.

---

## 1. Быстрый старт

```bash
vagrant up                 # создаёт db, затем app; при первом запуске генерирует deploy/secrets.env
vagrant ssh app            # или: ssh -p 2221 duma-admin@127.0.0.1
curl http://localhost:8000/health
cat deploy/secrets.env     # пароли admin/secretary для входа в веб-интерфейс
```

Без Vagrant (две готовые ВМ, команды от администратора):

```bash
# на сервере БД
export DB_OWNER_PASS=... DB_APP_PASS=... APP_SERVER_IP=172.27.206.10
sudo -E bash deploy/deploy_db.sh
# на сервере приложения
export DB_OWNER_PASS=... DB_APP_PASS=... ADMIN_PASSWORD=... SECRETARY_PASSWORD=... DB_SERVER_IP=172.27.206.20
sudo -E bash deploy/deploy_app.sh
```

Повторный запуск `deploy_app.sh` = обновление версии (код, зависимости, миграции, перезапуск).

## 2. Сетевая схема

```text
              Клиент (хост Windows/Linux)
                 │ http://localhost:8000          (проброс 8000 → app:8000)
                 │ ssh -p 2221 / -p 2220          (проброс → app:22 / db:22)
═════════════ VirtualBox NAT (enp0s3) ══════════════════════════════════
        │                                         │
┌───────▼──────────────────────────┐   ┌──────────▼───────────────────────┐
│ cityduma-app  172.27.206.10      │   │ cityduma-db   172.27.206.20      │
│ users: duma-admin (sudo, ключ)   │   │ users: duma-admin (sudo, ключ)   │
│        duma-app (nologin)        │   │        postgres                  │
│ /opt/cityduma  root:duma-app 750 │   │ БД city_duma                     │
│ /etc/cityduma  root:duma-app 750 │   │   duma_owner — владелец/миграции │
│ cityduma.service User=duma-app   │   │   duma_app   — только DML        │
│ iptables: 22, 8000; иначе DROP   │   │ iptables: 22; 5432 только с .10  │
└───────────────┬──────────────────┘   └──────────▲───────────────────────┘
                │   PostgreSQL :5432 (enp0s8, внутренняя сеть 172.27.206.0/24)
                └─────────────────────────────────┘
```

## 3. Выполнение требований

| № | Требование | Как выполнено | Где |
|---|---|---|---|
| 1 | Две Debian-подобные ВМ без GUI | `bento/ubuntu-24.04` (server, без GUI), app + db | `Vagrantfile` |
| 2 | Сеть, постоянная адресация, SSH по ключам | `private_network` со статическими IP (netplan внутри ВМ), вход только по ключу (`PasswordAuthentication no`) | `Vagrantfile`, `deploy/harden_ssh.sh` |
| 3 | Запрет root, отдельные пользователи | `PermitRootLogin no`; администратор `duma-admin` (sudo, пароль заблокирован, вход по ключу); приложение — системный `duma-app` (`nologin`, без домашнего каталога) | `deploy/harden_ssh.sh`, `deploy/deploy_app.sh` |
| 4 | Права на файлы и каталоги | код и venv — `root:duma-app`, каталоги 750, файлы 640: приложение читает, но не может изменить свой код; `/etc/cityduma` 750, `cityduma.env` 640 | `deploy/deploy_app.sh` |
| 5 | Среда выполнения и СУБД | Python 3 + venv, зависимости строго из `requirements.txt` (зафиксированные версии); PostgreSQL 16 | `deploy/deploy_*.sh` |
| 6 | БД и пользователь с минимальными правами | `duma_owner` — владелец схемы, используется только для миграций (пароль не сохраняется на сервере приложения); `duma_app` — только `SELECT/INSERT/UPDATE/DELETE` и последовательности, без `CREATE`; `pg_hba.conf` — только с `172.27.206.10`, `scram-sha-256`; PostgreSQL слушает только `localhost` и внутренний адрес | `deploy/deploy_db.sh` |
| 7 | Без контейнеров | uvicorn из venv | `deploy/deploy_app.sh` |
| 8 | systemd-служба: запуск/остановка/перезапуск/автостарт | `cityduma.service`, `systemctl enable` | `deploy/cityduma.service` |
| 9 | Перезапуск после аварии | `Restart=on-failure`, `RestartSec=5s`, ограничение `StartLimitBurst=5` за 120 с | `deploy/cityduma.service` |
| 10 | Firewall на **iptables** | политика `INPUT DROP`; app — 22 и 8000; db — 22 и 5432 только с `172.27.206.10` (остальные попытки — `LOG` с префиксом `DB-DENY`); правила сохраняются `netfilter-persistent` | `deploy/firewall.sh` |
| 11 | Настройки отдельно от кода | `/etc/cityduma/cityduma.env` → `EnvironmentFile=`; в репозитории только шаблон | `deploy/cityduma.env.template` |
| 12 | Скрипты повторения развёртывания | идемпотентные `deploy_db.sh`, `deploy_app.sh`, `harden_ssh.sh`, `firewall.sh` | `deploy/` |
| 13 | Не root, нет лишних портов, нет паролей в репозитории | `User=duma-app` + `NoNewPrivileges`, `ProtectSystem=strict`; открыты только 22/8000 и 22/5432(app); пароли — переменные окружения, `deploy/secrets.env` генерируется локально и в `.gitignore`, gitleaks в CI | см. раздел 4 |

## 4. Зафиксированные требования безопасности

1. **Приложение не запускается от root**: `User=duma-app`, `NoNewPrivileges=yes`; проверка — `ps -o user= -C uvicorn` → `duma-app`.
2. **Лишние порты не открыты**: `sudo iptables -L INPUT -n -v` — политика `DROP`, разрешены только порты роли; `ss -tlnp` на db показывает 5432 только на `127.0.0.1` и `172.27.206.20`.
3. **Пароли не хранятся в репозитории**: скрипты требуют `DB_OWNER_PASS`, `DB_APP_PASS`, `ADMIN_PASSWORD`, `SECRETARY_PASSWORD` из окружения и завершаются с ошибкой, если их нет; `deploy/secrets.env` — в `.gitignore`; шаблоны содержат только заглушки.
4. **Вход по SSH только по ключам**, root запрещён: `sudo sshd -T | grep -E 'permitrootlogin|passwordauthentication'`.

## 5. Проверка на защите

### 5.1 Перезагрузка обеих машин и автозапуск
```bash
vagrant reload             # или sudo reboot на каждой ВМ
# db:
systemctl is-enabled postgresql && systemctl is-active postgresql
sudo iptables -L INPUT -n | head -3          # правила восстановлены после перезагрузки
# app:
systemctl is-enabled cityduma && systemctl is-active cityduma
curl -s http://127.0.0.1:8000/health         # {"status":"ok","database":"ok",...}
```

### 5.2 Остановка БД и диагностика приложения
```bash
# db:
sudo systemctl stop postgresql
# app:
curl -s http://127.0.0.1:8000/health          # "database":"error: ..." — приложение живо, БД недоступна
sudo journalctl -u cityduma -n 20 --no-pager  # ERROR cityduma: health: database unavailable: ...
nc -zv 172.27.206.20 5432                     # Connection refused
# db:
sudo systemctl start postgresql               # app снова "database":"ok"
```

### 5.3 Процесс, порт и журналы средствами Linux
```bash
systemctl status cityduma --no-pager          # PID, Main PID, состояние
ps -o pid,user,cmd -C uvicorn                 # пользователь duma-app
sudo ss -tlnp | grep 8000                     # порт и процесс
sudo journalctl -u cityduma -f                # журнал службы (каждый запрос: метод, путь, код)
# аварийное завершение → автоматический перезапуск:
sudo kill -9 "$(systemctl show -p MainPID --value cityduma)"; sleep 6; systemctl is-active cityduma
```

### 5.4 Изменение параметра службы и восстановление
```bash
sudo systemctl edit cityduma        # добавить в override:  [Service]  Environment=LOG_LEVEL=DEBUG
sudo systemctl restart cityduma
systemctl show cityduma -p Environment
sudo journalctl -u cityduma -n 5    # появились DEBUG-сообщения
sudo systemctl revert cityduma && sudo systemctl restart cityduma   # возврат к исходному unit-файлу
```

### 5.5 Недоступность БД с постороннего узла
```bash
# с хоста (посторонний узел):
nc -zv -w 3 172.27.206.20 5432       # timeout (PowerShell: Test-NetConnection 172.27.206.20 -Port 5432 → False)
# на db: попытка видна в журнале ядра
sudo journalctl -k | grep DB-DENY | tail -1
sudo iptables -L INPUT -n -v --line-numbers
# с app (доверенный узел):
nc -zv 172.27.206.20 5432            # succeeded
```

## 6. Файлы

| Файл | Назначение |
|---|---|
| [`Vagrantfile`](../../Vagrantfile) | две ВМ, статические адреса, генерация `deploy/secrets.env`, запуск скриптов |
| [`deploy/harden_ssh.sh`](../../deploy/harden_ssh.sh) | администратор `duma-admin`, SSH только по ключам, запрет root |
| [`deploy/firewall.sh`](../../deploy/firewall.sh) | правила iptables для ролей `app` / `db` + сохранение |
| [`deploy/deploy_db.sh`](../../deploy/deploy_db.sh) | PostgreSQL, роли `duma_owner` / `duma_app`, `pg_hba.conf` |
| [`deploy/deploy_app.sh`](../../deploy/deploy_app.sh) | пользователь, код, venv, конфигурация, миграции, служба, проверка `/health` |
| [`deploy/cityduma.service`](../../deploy/cityduma.service) | unit-файл systemd |
| [`deploy/cityduma.env.template`](../../deploy/cityduma.env.template) | шаблон конфигурации службы (без значений) |
| [`deploy/secrets.env.example`](../../deploy/secrets.env.example) | список секретов развёртывания (без значений) |
| [`checklist.md`](checklist.md) | краткая шпаргалка для защиты |

---

## ❓ Ответы на основные вопросы

**Почему две машины?** Разделение ролей: взлом/падение приложения не даёт прямого доступа к БД, БД закрыта от всех, кроме сервера приложения.

**Как сделана постоянная адресация?** В `Vagrantfile` у каждой ВМ `private_network` с фиксированным IP (172.27.206.10 / .20); внутри ВМ это настройка netplan, которая сохраняется после перезагрузки.

**Как устроен вход по SSH?** Только по ключу: в `/etc/ssh/sshd_config.d/10-cityduma.conf` `PasswordAuthentication no`, `PermitRootLogin no`. Администратор — `duma-admin` (sudo, пароль заблокирован). Проверка: `sudo sshd -T | grep -E 'permitroot|passwordauth'`.

**От кого работает приложение и почему?** От системного пользователя `duma-app` без shell и домашнего каталога. Код принадлежит root — приложение может его читать, но не изменить. Взлом приложения не даёт прав root.

**Зачем два пользователя БД?** `duma_owner` — владелец схемы, только для миграций при развёртывании (пароль на сервере не хранится). `duma_app` — для работы приложения: только SELECT/INSERT/UPDATE/DELETE, создавать и удалять таблицы не может. Это «минимально необходимые права».

**Как ограничен доступ к БД?** Три уровня: iptables пускает 5432 только с 172.27.206.10; PostgreSQL слушает только внутренний адрес; `pg_hba.conf` разрешает вход только этим двум пользователям только с этого адреса.

**Объясни правила iptables.** Политика `INPUT DROP` (всё запрещено), разрешены: loopback, ответы на наши соединения (`ESTABLISHED,RELATED`), ping, SSH 22; на app — 8000, на db — 5432 только от сервера приложения (остальные попытки пишутся в журнал с префиксом `DB-DENY`). Правила сохраняются `netfilter-persistent` и восстанавливаются после перезагрузки.

**Что в unit-файле systemd?** `User=duma-app`; `EnvironmentFile=/etc/cityduma/cityduma.env` (настройки отдельно от кода); `Restart=on-failure` + `RestartSec=5s` — перезапуск после аварии, `StartLimitBurst` — не больше 5 раз за 2 минуты; `TimeoutStopSec` — корректная остановка; `NoNewPrivileges`, `ProtectSystem=strict` — ограничения процесса; `WantedBy=multi-user.target` + `systemctl enable` — автозапуск.

**Где настройки и пароли?** На сервере — `/etc/cityduma/cityduma.env` (права 640, root:duma-app). В репозитории — только шаблоны; при `vagrant up` пароли генерируются в `deploy/secrets.env`, который в `.gitignore`.

**Как найти процесс, порт, журнал?** `systemctl status cityduma`, `ps -o user,pid,cmd -C uvicorn`, `sudo ss -tlnp | grep 8000`, `journalctl -u cityduma -f`.

**Что будет, если остановить БД?** Приложение продолжит работать, `/health` покажет `database: error`, в журнале появится ошибка; после запуска БД всё восстановится само.
