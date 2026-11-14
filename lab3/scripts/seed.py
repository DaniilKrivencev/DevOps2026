"""Наполнение БД демонстрационными данными (для проверки миграций и бэкапов).

Используется «сырой» SQL только по столбцам исходной схемы (ревизия 0001),
поэтому скрипт работает на любой ревизии — это нужно, чтобы наполнить
старую БД и затем проверить её обновление миграциями.
"""

import asyncio

from sqlalchemy import text

from app.database import AsyncSessionLocal, engine

DEPUTIES = [
    ("Иванов Иван Иванович", "Партия А", "№1"),
    ("Петрова Анна Сергеевна", "Партия Б", "№2"),
    ("Сидоров Олег Петрович", "Партия А", "№3"),
]


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        if (await db.execute(text("SELECT count(*) FROM deputies"))).scalar():
            print("БД уже содержит данные — пропуск наполнения")
            return
        for full_name, party, district in DEPUTIES:
            await db.execute(
                text(
                    "INSERT INTO deputies (full_name, party, district, is_active) "
                    "VALUES (:n, :p, :d, :a)"
                ),
                {"n": full_name, "p": party, "d": district, "a": True},
            )
        await db.execute(
            text("INSERT INTO commissions (name, description) VALUES (:n, :d)"),
            {"n": "Комиссия по бюджету", "d": "Бюджет города"},
        )
        commission_id = (await db.execute(text("SELECT max(id) FROM commissions"))).scalar()
        ids = (await db.execute(text("SELECT id FROM deputies ORDER BY id"))).scalars().all()
        for deputy_id in ids:
            await db.execute(
                text("INSERT INTO commission_members (commission_id, deputy_id) VALUES (:c, :d)"),
                {"c": commission_id, "d": deputy_id},
            )
        await db.execute(
            text("UPDATE commissions SET chair_id = :d WHERE id = :c"),
            {"d": ids[0], "c": commission_id},
        )
        await db.execute(
            text(
                "INSERT INTO sessions (commission_id, held_on, topic, status) "
                "VALUES (:c, '2026-10-01', 'Бюджет-2027', 'planned')"
            ),
            {"c": commission_id},
        )
        await db.commit()
        print(f"Добавлено: депутатов {len(DEPUTIES)}, комиссий 1, заседаний 1")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
