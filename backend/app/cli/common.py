from __future__ import annotations

from datetime import date


def parse_cli_date(s: str) -> date:
    return date.fromisoformat(s)
