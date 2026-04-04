#!/usr/bin/env python3
"""Print row counts for each table in the app database (same DATABASE_URL as the backend).

Usage (from repository root)::

    python scripts/db_row_counts.py

With explicit env::

    DATABASE_URL=sqlite:////path/to/app.db python scripts/db_row_counts.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import inspect, text  # noqa: E402

from backend.app.data.database import engine  # noqa: E402


def main() -> int:
    insp = inspect(engine)
    names = sorted(insp.get_table_names())
    if not names:
        print("(no tables)", file=sys.stderr)
        return 0
    total = 0
    with engine.connect() as conn:
        for name in names:
            n = int(conn.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar_one())
            total += n
            print(f"{name}\t{n}")
    print(f"TOTAL\t{total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
