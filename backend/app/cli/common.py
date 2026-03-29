from __future__ import annotations

from datetime import date
from pathlib import Path


def parse_cli_date(s: str) -> date:
    return date.fromisoformat(s)


def load_symbols_from_path(path: Path) -> list[str]:
    """Load tickers from a text file: one per line, optional comma-separated tokens, ``#`` comments.

    Skips a lone header line ``symbol`` / ``ticker`` (case-insensitive). De-duplicates preserving order.
    """
    raw = path.read_text(encoding="utf-8")
    out: list[str] = []
    for ln in raw.splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if "," in s:
            out.extend(p.strip().upper() for p in s.split(",") if p.strip())
        else:
            if s.lower() in ("symbol", "ticker"):
                continue
            out.append(s.upper())
    return list(dict.fromkeys(out))
