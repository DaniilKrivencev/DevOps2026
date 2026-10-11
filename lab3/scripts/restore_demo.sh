#!/usr/bin/env bash
# Демонстрация п. 12: восстановление данных после намеренного удаления и изменения.
# Работает с текущей БД из конфигурации (SQLite или PostgreSQL).
set -euo pipefail

PY=${PY:-python}
count() {
  $PY - <<'PYEOF'
import asyncio
from sqlalchemy import text
from app.database import engine
async def main():
    async with engine.connect() as c:
        n = (await c.execute(text("SELECT count(*) FROM deputies"))).scalar()
        names = (await c.execute(text("SELECT full_name FROM deputies ORDER BY id"))).scalars().all()
    await engine.dispose()
    print(f"  депутатов: {n} {list(names)}")
asyncio.run(main())
PYEOF
}

echo "▶ 1. Миграции и демо-данные"
$PY -m alembic upgrade head
$PY -m scripts.seed
count

echo "▶ 2. Резервная копия"
mkdir -p backups
EXT=$($PY -c "from app.config import get_database_url as u; print('sqlite' if u().startswith('sqlite') else 'sql')")
DUMP="backups/restore_demo.$EXT"
$PY -m scripts.db_backup backup --output "$DUMP"

echo "▶ 3. Намеренное удаление и изменение данных"
$PY - <<'PYEOF'
import asyncio
from sqlalchemy import text
from app.database import engine
async def main():
    async with engine.begin() as c:
        await c.execute(text("DELETE FROM attendances"))
        await c.execute(text("UPDATE commissions SET chair_id = NULL"))
        await c.execute(text("DELETE FROM deputies WHERE full_name LIKE 'Петрова%'"))
        await c.execute(text("UPDATE deputies SET full_name = 'ИСПОРЧЕНО' WHERE full_name LIKE 'Иванов%'"))
    await engine.dispose()
asyncio.run(main())
PYEOF
count

echo "▶ 4. Восстановление из $DUMP"
$PY -m scripts.db_backup restore "$DUMP"
count
echo "✔ Данные восстановлены"
