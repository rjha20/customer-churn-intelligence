from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "data" / "processed" / "local" / "retention.sqlite"
QUERY_FILE = ROOT / "sql" / "retention_review.sql"


def main() -> None:
    if not DATABASE.exists():
        raise FileNotFoundError("Run `uv run python scripts/run_pipeline.py` first")
    with sqlite3.connect(DATABASE) as connection:
        statements = [part.strip() for part in QUERY_FILE.read_text(encoding="utf-8-sig").split(";") if part.strip()]
        query_number = 0
        for statement in statements:
            if "SELECT" not in statement.upper():
                continue
            query_number += 1
            cursor = connection.execute(statement)
            headers = [column[0] for column in cursor.description or []]
            rows = cursor.fetchall()
            print(f"\nQuery {query_number} ({len(rows)} rows)")
            print(" | ".join(headers))
            for row in rows[:40]:
                print(" | ".join(str(value) for value in row))
            if len(rows) > 40:
                print(f"... {len(rows) - 40} additional grouped rows omitted")


if __name__ == "__main__":
    main()
