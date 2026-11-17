# Лабораторная работа №7: Управление конфигурацией и воспроизводимая инфраструктура

> ## ▶ Как запустить и показать
>
> Нужны **VirtualBox + Vagrant**. Ansible ставить не нужно — он работает в контейнере
> (`scripts/infra.sh`), поэтому команды выполняются на ВМ `docker` (там есть Docker и make):
> ```bash
> vagrant up docker infra-stage infra-prod     # ВМ с Docker + две ЧИСТЫЕ ВМ (staging и production)
> vagrant ssh docker
> cd /opt/cityduma-src
>
> make infra-lint                     # проверка кода: yamllint, ansible-lint, синтаксис, требования
> make infra-check ENV=staging        # что будет изменено (ничего не меняет)
> make infra-apply ENV=staging        # подготовка чистой машины → приложение работает и проверено
> make infra-apply ENV=staging        # повторно: в итоге changed=0
> make infra-apply ENV=production     # второе окружение
> make infra-test                     # всё сразу на одноразовой «чистой машине» (как в CI)
> ```
> Пароль к секретам: файл `infra/ansible/.vault_pass` (его нет в Git — хранится у команды,
> в GitHub — секрет `ANSIBLE_VAULT_PASSWORD`). Приложение staging: **http://localhost:8280**,
> production: **http://localhost:8380**.

## 1. Что сделано

```
infra/ansible/
├── ansible.cfg, requirements.txt, Dockerfile, run.sh   управляющий узел (Ansible 2.21 в контейнере)
├── site.yml                  все роли по порядку;  verify.yml — только проверка
├── group_vars/all.yml        ОБЩИЕ параметры
├── inventories/
│   ├── staging/              окружение staging: hosts.yml, group_vars/cityduma/{main,vault}.yml, host_vars/
│   ├── production/           окружение production
│   └── ci/                   «чистая машина» для pipeline (секреты генерируются на лету)
├── roles/
│   ├── base       проверка ОС, базовые пакеты, имя узла
│   ├── users      duma-admin (sudo, только ключ), cd-deploy (pipeline, ключ ограничен командой)
│   ├── ssh        шаблон sshd: без паролей и root, AllowUsers; проверка sshd -t до применения
│   ├── firewall   шаблоны iptables rules.v4/v6, обнаружение ручных изменений и восстановление
│   ├── docker     Docker Engine + Compose, шаблон daemon.json
│   ├── app        каталоги и права, .env из шаблона и vault, compose, запуск — только при расхождении
│   └── verify     /health, /version, основной сценарий, открытые порты, firewall, права на секреты
└── test/          «чистая машина» (Dockerfile) и сценарий make infra-test
```

| Файл вне `infra/` | Назначение |
|---|---|
| [`.github/workflows/infra.yml`](../../.github/workflows/infra.yml) | отдельный pipeline инфраструктуры |
| [`scripts/infra.sh`](../../scripts/infra.sh) | запуск Ansible в управляющем контейнере |
| [`scripts/infra_policy.py`](../../scripts/infra_policy.py) | требования к инфраструктурному коду (+ тесты `tests/unit/test_infra_policy.py`) |
| [`Vagrantfile`](../../Vagrantfile) | чистые ВМ `infra-stage` (172.27.206.60) и `infra-prod` (172.27.206.70) |
| [`.github/CODEOWNERS`](../../.github/CODEOWNERS) | обязательное согласование ролей, окружений и секретов |

## 2. Выполнение задания

| № | Пункт | Решение |
|---|---|---|
| 1 | Средство управления конфигурацией | **Ansible** (ansible-core 2.21.6), только встроенные модули `ansible.builtin` — нет внешних зависимостей |
| 2 | Целевые узлы; параметры общие / окружения / узловые / секретные | узлы — `inventories/*/hosts.yml`; общие — `group_vars/all.yml`; окружения — `inventories/<env>/group_vars/cityduma/main.yml`; узловые — `host_vars/<узел>.yml`; секретные — `vault.yml` (ansible-vault) |
| 3 | Подготовка чистой Linux-машины | ВМ `infra-stage`/`infra-prod` без провижининга; в CI — новый контейнер-сервер при каждом запуске |
| 4 | Пользователи, SSH, пакеты, Docker, каталоги, права, firewall, конфигурация, сервисы | роли `users`, `ssh`, `base`, `docker`, `app` (каталоги и права), `firewall`, шаблоны конфигурации, `docker compose` и службы systemd |
| 5 | Шаблоны конфигурационных файлов | `sshd-cityduma.conf.j2`, `rules.v4.j2`/`rules.v6.j2`, `daemon.json.j2`, `env.j2`, `sudoers-admin.j2`, `authorized_keys-*.j2` |
| 6 | ≥ 2 окружения | `staging` и `production` (+ `ci`): разные уровни журнала, SSH в production — только из сети 172.27.206.0/24, свои секреты |
| 7 | Повторный запуск без необоснованных изменений | у всех `command` — `changed_when`; `docker compose up` запускается только при расхождении; iptables применяются только при отличии фактических правил; второй запуск — **changed=0** (проверяется автоматически) |
| 8 | Ручное изменение → восстановление | `make infra-test` меняет SSH, iptables, останавливает nginx, портит права `.env` → `--check --diff` показывает расхождения, ничего не меняя → обычный запуск восстанавливает всё → следующий снова `changed=0` |
| 9 | Нет незашифрованных секретов | `vault.yml` зашифрованы AES256; пароль vault не в Git; `infra_policy.py` проверяет шифрование и что в открытых файлах только ссылки `{{ vault_… }}`; задачи с секретами — `no_log`; gitleaks в CI |
| 10 | Проверка доступности после настройки | роль `verify` в конце каждого запуска + `make infra-verify` |
| 11 | Отдельный pipeline / CD | `.github/workflows/infra.yml`: проверка кода → чистая машина → применение к окружению (ручной запуск, production — с подтверждением) |
| 12 | Требования к инфраструктурному коду | раздел 3 — проверяются автоматически |
| 13 | Согласование критических ролей, шаблонов и секретов | `CODEOWNERS` для `infra/ansible/roles`, `inventories` (вкл. vault), `group_vars`, `site.yml`; этап `guard` (ЛР5) перечисляет их изменения |

## 3. Требования к инфраструктурному коду (п. 12)

| Требование | Как обеспечено | Чем проверяется |
|---|---|---|
| Нет лишних открытых портов | firewall открывает только `ssh_port` и `http_port`, политика `INPUT DROP`; наружу публикуется только nginx | `infra_policy.py` (список портов), роль `verify`: `ss -tln` — слушают только 22 и 8080 |
| Минимальные права | `.env` — 0640 root:cd-deploy; сценарий выпуска — root 0755; cd-deploy без sudo, ключ ограничен командой; duma-admin — без пароля; нет прав 0777/0666 | `infra_policy.py` (права), `verify` (права `.env`), ansible-lint `risky-file-permissions` |
| Нет необъяснимых shell-команд | модуль `shell` запрещён; `command` — только с комментарием «Обоснование:» и `changed_when` (их 9: чтение iptables и ss, iptables-restore, docker compose и docker login — встроенных модулей для этого нет) | `infra_policy.py`, ansible-lint `no-changed-when`, `command-instead-of-shell` |
| Повторяемость | идемпотентные модули, применение только при расхождении | второй запуск `changed=0` в `make infra-test` и в pipeline |

## 4. Как устроено обнаружение ручных изменений

- **Файлы** (sshd, daemon.json, .env, compose, шаблоны iptables) — шаблоны Ansible сравнивают содержимое,
  права и владельца; отличие → файл перезаписывается, служба перезапускается обработчиком.
- **Живые правила iptables** могут отличаться от файла (кто-то выполнил `iptables -I …`). Роль читает
  `iptables -S INPUT` и сравнивает с правилами из шаблона (они записаны в том же каноническом виде);
  при отличии — `iptables-restore --noflush` (цепочки Docker не затрагиваются).
- **Контейнеры** — `docker compose ps`: если сервис остановлен, нездоров или запущен не тот образ —
  `docker compose up --wait`.
- **Версия приложения**: первичную ставит Ansible (`app_tag`), дальше версии выпускает CD (ЛР6) и
  записывает в `state/current.tag` — Ansible её уважает и не откатывает выпущенный релиз.

## 5. Проверка на защите

```bash
vagrant ssh docker && cd /opt/cityduma-src

# 1. Подготовка чистой машины
vagrant destroy -f infra-stage && vagrant up infra-stage      # (на хосте) — новая чистая ВМ
make infra-apply ENV=staging                                  # итог: PLAY RECAP … failed=0, «Итог проверки»

# 2. Повторный запуск без необоснованных изменений
make infra-apply ENV=staging                                  # PLAY RECAP … changed=0

# 3. Восстановление вручную изменённой конфигурации
# на хосте: vagrant ssh infra-stage, затем
  sudo sed -i 's/^PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config.d/10-cityduma.conf
  sudo iptables -I INPUT -p tcp --dport 5432 -j ACCEPT
  sudo docker stop cityduma-nginx-1
make infra-check ENV=staging      # --diff показывает, что именно вернётся
make infra-apply ENV=staging      # changed=… — SSH, iptables, nginx восстановлены
make infra-apply ENV=staging      # снова changed=0

# 4. Проверка доступности приложения после настройки
make infra-verify ENV=staging     # /health, /version, основной сценарий, порты, firewall, права

# 5. Нет открытых секретов
head -1 infra/ansible/inventories/*/group_vars/cityduma/vault.yml   # $ANSIBLE_VAULT;1.1;AES256
make infra-vault-view ENV=staging                                    # расшифровка только с паролем
python3 -m scripts.infra_policy                                      # открытых значений нет
git check-ignore -v infra/ansible/.vault_pass                        # пароль vault не в Git
```

Всё то же автоматически: `make infra-test` и вкладка **Actions → Infrastructure (Ansible)**.

## 6. Настройка pipeline для применения к окружениям

GitHub → Settings → Environments → `staging` и `production` (для production — Required reviewers):
- секреты `ANSIBLE_VAULT_PASSWORD` (содержимое `infra/ansible/.vault_pass`) и `ANSIBLE_SSH_KEY`
  (закрытый ключ администратора; его публичная часть — в `vault_admin_ssh_pubkeys`);
- переменная `CD_RUNS_ON=["self-hosted","staging"]`, если ВМ во внутренней сети (как в ЛР6).

Запуск: Actions → Infrastructure (Ansible) → Run workflow → окружение и `check`/`apply`.
Этапы lint и «чистая машина» запускаются сами на каждый push с изменениями инфраструктуры.

---

## ❓ Ответы на основные вопросы

**Почему Ansible?** Без агента на серверах (нужны только SSH и Python), описание в YAML, огромный набор
готовых модулей, идемпотентность «из коробки». В задании он указан как пример.

**Что такое идемпотентность и как её добиться?** Повторный запуск не меняет то, что уже в нужном
состоянии. Модули Ansible (`apt`, `template`, `user`, `file`) сами сравнивают текущее и требуемое
состояние. Где модуля нет и используется `command`, мы явно говорим, когда это изменение
(`changed_when`), и выполняем команду только при расхождении. Проверка — второй запуск: `changed=0`.

**Как разделены параметры?** Общие (`group_vars/all.yml`: пути, имена пользователей, порт) →
окружения (`inventories/<env>/group_vars/cityduma/main.yml`: уровень журнала, откуда пускать SSH,
версия) → секретные (`vault.yml` рядом, зашифрован) → узловые (`host_vars`: адрес, имя узла).
Окружение переопределяет общие, узел — окружение.

**Как хранятся секреты?** В `vault.yml` каждого окружения, зашифрованы `ansible-vault` (AES256).
Пароль от vault — не в Git: локально файл `.vault_pass` (в `.gitignore`), в CI — защищённый секрет.
В открытых файлах — только ссылки `{{ vault_postgres_password }}`; задачи с секретами — `no_log: true`,
поэтому пароли не попадают в журнал.

**Что такое шаблон?** Файл Jinja2 (`*.j2`), в который подставляются переменные окружения: например
`sshd-cityduma.conf.j2` → `/etc/ssh/sshd_config.d/10-cityduma.conf`. Один шаблон — разные значения
для staging и production.

**Как Ansible узнаёт о ручном изменении?** Сравнивает требуемое состояние с фактическим: содержимое
и права файлов, фактические правила iptables, состояние контейнеров. Отличие → исправляет и
показывает `changed`; `--check --diff` показывает это без применения.

**Почему нельзя просто `shell`?** Shell-команда непрозрачна: неясно, что она меняет, и она
выполняется каждый раз. Поэтому `shell` запрещён, а каждый `command` объяснён комментарием
и имеет `changed_when` — это проверяет `scripts/infra_policy.py`.

**Чем отличаются окружения?** staging — отладочный журнал, SSH из любой сети; production — журнал
INFO, SSH только из административной сети 172.27.206.0/24, применение — с подтверждением в GitHub.

**Как это связано с ЛР6?** Ansible готовит окружение (пользователи, Docker, firewall, конфигурация,
учётная запись `cd-deploy` и сценарий выпуска) и ставит первую версию. Дальше новые версии выпускает
CD — и Ansible их не откатывает (читает `state/current.tag`).

**Почему `vagrant ssh infra-prod` не пускает после настройки?** Так и задумано: в production SSH
разрешён только из административной сети 172.27.206.0/24, а `vagrant ssh` идёт через NAT (10.0.2.2).
Входить с ВМ `docker` или с хоста по адресу: `ssh -i .vagrant/machines/infra-prod/virtualbox/private_key vagrant@172.27.206.70`.

**Что проверяется после настройки?** `/health` (приложение и БД), `/version` (та версия), основной
сценарий пользователя, что наружу слушают только 22 и 8080, что firewall в режиме DROP и что у файла
секретов права 0640.
