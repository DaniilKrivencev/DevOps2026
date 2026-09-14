# Описание API — Городская Дума

Base URL: `http://localhost:8000/api/v1`

Интерактивная документация: `http://localhost:8000/docs`

---

## Коды ответов

| Код | Значение |
|-----|----------|
| 200 | Успешный запрос |
| 201 | Ресурс создан |
| 204 | Успешно, без тела ответа |
| 404 | Ресурс не найден |
| 409 | Конфликт (дубликат) |
| 422 | Ошибка валидации или нарушение бизнес-правила |

---

## Health Check

```
GET /health
```

**Ответ:**
```json
{
  "status": "ok",
  "database": "ok",
  "version": "0.1.0"
}
```

---

## Депутаты `/deputies`

### GET /deputies/
Список всех депутатов.

### POST /deputies/
Создать депутата.
```json
{
  "full_name": "Иванов Иван Иванович",
  "party": "Единая Россия",
  "district": "Округ №1",
  "elected_on": "2023-09-10",
  "is_active": true
}
```

### GET /deputies/{id}
Получить депутата по ID.

### PATCH /deputies/{id}
Изменить поля депутата (частичное обновление).

### DELETE /deputies/{id}
Удалить депутата.

---

## Комиссии `/commissions`

### GET /commissions/
### POST /commissions/
```json
{
  "name": "Комиссия по бюджету",
  "description": "Рассматривает вопросы городского бюджета",
  "chair_id": null
}
```

> ⚠️ **Бизнес-правило**: `chair_id` должен быть членом комиссии.
> Установка председателя-не-члена возвращает HTTP 422.

### GET /commissions/{id}
### PATCH /commissions/{id}
### DELETE /commissions/{id}

### GET /commissions/{id}/members
Состав комиссии.

### POST /commissions/{id}/members
Добавить члена.
```json
{
  "deputy_id": 1,
  "joined_on": "2024-01-15"
}
```

### DELETE /commissions/{id}/members/{deputy_id}
Удалить члена. Председателя удалить нельзя (HTTP 422).

---

## Заседания `/sessions`

### GET /sessions/
### POST /sessions/
```json
{
  "commission_id": 1,
  "held_on": "2026-10-15",
  "topic": "Обсуждение проекта бюджета на 2027 год",
  "status": "planned",
  "notes": null
}
```

Статусы: `planned`, `held`, `cancelled`

> ⚠️ **Бизнес-правило**: перевод в статус `held` проверяет кворум.
> Если присутствующих ≤ 50% членов комиссии → HTTP 422.

### GET /sessions/{id}
### PATCH /sessions/{id}
### DELETE /sessions/{id}

---

## Посещаемость `/attendance`

### GET /attendance/?session_id=&deputy_id=
Фильтрация по заседанию и/или депутату.

### POST /attendance/
```json
{
  "session_id": 1,
  "deputy_id": 2,
  "status": "present",
  "note": null
}
```

Статусы: `present`, `absent`, `excused`

> Дублирующая запись (один депутат + одно заседание) → HTTP 409.

### GET /attendance/{id}
### PATCH /attendance/{id}
### DELETE /attendance/{id}
