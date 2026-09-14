# Городская Дума — City Council Management System

> Система учёта депутатов, комиссий, заседаний и посещаемости городской думы.

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)](https://docker.com)

---

## Назначение системы

Веб-приложение для учёта:
- **Депутатов** (ФИО, партия, округ, дата избрания, статус)
- **Комиссий** (название, описание, председатель, состав)
- **Заседаний** (дата, тема, статус, привязка к комиссии)
- **Посещаемости** (явка депутатов на заседания)

## Пользователи системы

| Роль | Описание |
|------|----------|
| Администратор | Полный доступ ко всем операциям |
| Секретарь | Ведёт заседания и посещаемость |
| Пользователь | Просмотр данных |

## Правила предметной области

1. **Председатель комиссии** обязан быть её членом. Попытка назначить председателем не-члена возвращает HTTP 422.
2. **Кворум**: заседание можно пометить как «Проведено» только если на нём присутствовало более 50% членов комиссии.
3. **Удаление председателя** из членов комиссии запрещено без смены председателя.
4. Одна запись посещаемости на пару «депутат + заседание» (уникальность гарантируется на уровне БД).

---

## Быстрый старт (Docker)

```bash
# 1. Клонировать репозиторий
git clone <repo-url>
cd DevOps

# 2. Создать .env
cp .env.example .env
# Отредактируйте .env — смените пароли!

# 3. Запустить
make up

# 4. Открыть браузер
# Веб-интерфейс: http://localhost:8000
# API документация: http://localhost:8000/docs
# Health check: http://localhost:8000/health
```

## Локальная разработка

```bash
# Первоначальная настройка
make setup

# Применить миграции (нужен PostgreSQL)
make migrate

# Запустить приложение
make run

# Запустить тесты (SQLite, без PostgreSQL)
make test

# Проверка качества кода
make quality

# Полная проверка перед коммитом
make verify
```

---

## Структура проекта

```
DevOps/
├── app/
│   ├── main.py          # Точка входа FastAPI
│   ├── database.py      # Настройка SQLAlchemy
│   ├── models.py        # ORM-модели
│   ├── schemas.py       # Pydantic-схемы
│   ├── routers/         # CRUD-роутеры по сущностям
│   └── templates/       # HTML-шаблоны (Jinja2)
├── alembic/             # Миграции БД
│   └── versions/
├── tests/               # Автоматические тесты
├── docs/
│   ├── API.md           # Описание API
│   └── schema.md        # Схема данных
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── requirements.txt
├── pyproject.toml
├── .env.example
├── .gitignore
├── CONTRIBUTING.md      # Правила внесения изменений
└── README.md
```

---

## API

Полное описание — в [docs/API.md](docs/API.md).

Краткий обзор:

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/health` | Проверка работоспособности |
| GET/POST | `/api/v1/deputies/` | Список / создание депутатов |
| GET/PATCH/DELETE | `/api/v1/deputies/{id}` | Детали / изменение / удаление |
| GET/POST | `/api/v1/commissions/` | Список / создание комиссий |
| GET/POST/DELETE | `/api/v1/commissions/{id}/members` | Состав комиссии |
| GET/POST | `/api/v1/sessions/` | Заседания |
| GET/POST | `/api/v1/attendance/` | Посещаемость |

---

## Схема данных

Подробно — в [docs/schema.md](docs/schema.md).

```
Deputy 1──* CommissionMember *──1 Commission
                                    │
                               1    │
                               *    │
                             Session
                               │
                          1   │
                          *   │
                        Attendance──*──1 Deputy
```

---

## Конфигурация через переменные окружения

| Переменная | Обязательна | Описание |
|---|---|---|
| `DATABASE_URL` | ✅ | DSN для подключения к PostgreSQL |
| `POSTGRES_USER` | ✅ | Пользователь БД |
| `POSTGRES_PASSWORD` | ✅ | Пароль БД |
| `POSTGRES_DB` | ✅ | Имя базы данных |
| `SECRET_KEY` | ✅ | Ключ для секретов |
| `APP_ENV` | — | `development` / `production` |
| `DEBUG` | — | `true` / `false` |

Шаблон: [`.env.example`](.env.example). **Файл `.env` никогда не коммитится!**

---

## Команды Makefile

| Команда | Описание |
|---|---|
| `make setup` | Первоначальная настройка (venv, зависимости) |
| `make run` | Локальный запуск |
| `make test` | Автоматические тесты |
| `make quality` | Форматирование и анализ (ruff) |
| `make migrate` | Применение миграций |
| `make backup` | Резервная копия БД |
| `make restore BACKUP=...` | Восстановление из резервной копии |
| `make verify` | Полный набор проверок (quality + test) |
| `make up` | Запуск Docker-окружения |
| `make down` | Остановка Docker-окружения |
| `make container-check` | Проверка health endpoint |

---

## Лицензия

Учебный проект. © 2026
