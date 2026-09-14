# Схема данных — Городская Дума

## Диаграмма сущностей (ERD)

```
┌──────────────┐          ┌─────────────────────┐          ┌──────────────┐
│   deputies   │          │  commission_members  │          │ commissions  │
├──────────────┤     ┌────┤──────────────────────├────┐     ├──────────────┤
│ id PK        │     │    │ id PK                │    │     │ id PK        │
│ full_name    │◄────┘    │ commission_id FK──────────►     │ name UNIQUE  │
│ party        │          │ deputy_id FK          │         │ description  │
│ district     │          │ joined_on             │         │ chair_id FK──►─┐
│ elected_on   │          └─────────────────────┘          │ created_at   │ │
│ is_active    │                                            └──────────────┘ │
│ created_at   │◄──────────────────────────────────────────────────────────┘
└──────┬───────┘
       │
       │ 1..*
       ▼
┌──────────────┐          ┌──────────────┐
│  attendances │          │   sessions   │
├──────────────┤          ├──────────────┤
│ id PK        │          │ id PK        │
│ session_id FK├─────────►│ commission_id FK
│ deputy_id FK │          │ held_on      │
│ status ENUM  │          │ topic        │
│ note         │          │ status ENUM  │
│ UNIQUE(session│         │ notes        │
│  _id,deputy_id│         │ created_at   │
└──────────────┘          └──────────────┘
```

## Таблицы

### deputies
| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK, AUTO | Первичный ключ |
| full_name | VARCHAR(200) | NOT NULL | ФИО депутата |
| party | VARCHAR(100) | | Политическая партия |
| district | VARCHAR(100) | | Избирательный округ |
| elected_on | DATE | | Дата избрания |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Активен ли |
| created_at | TIMESTAMPTZ | DEFAULT now() | Дата создания записи |

### commissions
| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK, AUTO | Первичный ключ |
| name | VARCHAR(200) | NOT NULL, UNIQUE | Название комиссии |
| description | TEXT | | Описание |
| chair_id | INTEGER | FK → deputies.id, ON DELETE SET NULL | Председатель |
| created_at | TIMESTAMPTZ | DEFAULT now() | Дата создания |

### commission_members
| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK, AUTO | Первичный ключ |
| commission_id | INTEGER | FK → commissions.id CASCADE | Комиссия |
| deputy_id | INTEGER | FK → deputies.id CASCADE | Депутат |
| joined_on | DATE | | Дата вступления |
| | | UNIQUE(commission_id, deputy_id) | Уникальность |

### sessions
| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK, AUTO | Первичный ключ |
| commission_id | INTEGER | FK → commissions.id CASCADE, NOT NULL | Комиссия |
| held_on | DATE | NOT NULL | Дата заседания |
| topic | VARCHAR(500) | NOT NULL | Тема |
| status | ENUM | NOT NULL, DEFAULT 'planned' | planned/held/cancelled |
| notes | TEXT | | Примечания |
| created_at | TIMESTAMPTZ | DEFAULT now() | Дата создания |

### attendances
| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK, AUTO | Первичный ключ |
| session_id | INTEGER | FK → sessions.id CASCADE, NOT NULL | Заседание |
| deputy_id | INTEGER | FK → deputies.id CASCADE, NOT NULL | Депутат |
| status | ENUM | NOT NULL, DEFAULT 'present' | present/absent/excused |
| note | VARCHAR(300) | | Примечание (причина) |
| | | UNIQUE(session_id, deputy_id) | Уникальность |

## Бизнес-правила на уровне приложения

1. `commissions.chair_id` → депутат должен присутствовать в `commission_members` для данной комиссии.
2. `sessions.status = 'held'` разрешено только при кворуме: `COUNT(attendances WHERE status='present') > COUNT(commission_members) / 2`.
3. Нельзя удалить запись из `commission_members`, если `deputy_id` равен `commissions.chair_id`.
