# История версий

Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/), версии — [SemVer](https://semver.org/lang/ru/).

## [0.5.0] — ЛР4, ЛР5 и доработки ЛР1–ЛР3

### Добавлено
- Авторизация HTTP Basic с ролями `admin` / `secretary` (ЛР1).
- Журналирование запросов и ошибок, request id, формат text/json (ЛР1).
- Развёртывание на двух ВМ: iptables, SSH только по ключам, администратор `duma-admin`,
  роли БД `duma_owner` / `duma_app`, пароли вне репозитория (ЛР2).
- Контейнеризация: Dockerfile, Compose (db, migrate, 2 экземпляра приложения, nginx),
  `make container-check` (ЛР4).
- CI в GitHub Actions: этапы в Docker-in-Docker, тестовая БД, кэш, тег по SHA,
  блокировка публикации, CODEOWNERS и этап guard (ЛР5).
- `requirements.lock`, `make audit`, `make ci`.

### Изменено
- Единая кодовая база в корне репозитория (бывший каталог `lab3/`).
- Зависимости обновлены: fastapi 0.163.2 (starlette 1.10.0), jinja2 3.1.6, python-dotenv 1.2.4.

### Безопасность
- Из репозитория удалены локальные ключи Vagrant (`.vagrant/`) и пароли из скриптов развёртывания.

## [0.3.0] — ЛР3
Автоматические проверки (`make verify`), миграции 0002–0004, резервное копирование.

## [0.1.0] — ЛР1
Первая версия: API, веб-интерфейс, PostgreSQL, `/health`, Git-процесс.
