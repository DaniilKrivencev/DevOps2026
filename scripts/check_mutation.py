"""Проверка порога мутационного тестирования по кэшу mutmut (.mutmut-cache)."""

import sqlite3
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    threshold = int(argv[1]) if len(argv) > 1 else 90
    cache = Path(".mutmut-cache")
    if not cache.exists():
        print("✗ .mutmut-cache не найден — сначала выполните mutmut run")
        return 1
    with sqlite3.connect(cache) as conn:
        rows = dict(conn.execute("SELECT status, count(*) FROM Mutant GROUP BY status"))
    killed = rows.get("ok_killed", 0)
    total = sum(rows.values())
    score = killed * 100 / total if total else 0.0
    print(f"Мутанты: всего {total}, убито {killed}, статусы {rows} → score {score:.1f}%")
    if score < threshold:
        print(f"✗ Mutation score ниже порога {threshold}%")
        return 1
    print(f"✔ Mutation score ≥ {threshold}%")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
