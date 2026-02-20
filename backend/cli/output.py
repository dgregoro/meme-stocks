"""Output formatters: table and JSON.

Table: human-readable for terminals.
JSON: raw for scripting.
"""

from __future__ import annotations

import json
import os
from typing import Any


def get_output_format() -> str:
    """Output format from env (table or json)."""
    return os.environ.get("MEME_STOCKS_OUTPUT", "table").lower()


def print_table(headers: list[str], rows: list[list[Any]], max_col_width: int = 40) -> None:
    """Print a simple ASCII table."""
    if not headers:
        return
    col_widths = []
    for i, h in enumerate(headers):
        w = min(len(str(h)), max_col_width)
        for row in rows:
            if i < len(row):
                w = max(w, min(len(str(row[i])), max_col_width))
        col_widths.append(min(w, max_col_width))

    def cell(val: Any, width: int) -> str:
        s = str(val)
        if len(s) > width:
            return s[: width - 1] + "…"
        return s.ljust(width)

    header_line = "  ".join(cell(h, col_widths[i]) for i, h in enumerate(headers))
    print(header_line)
    print("-" * len(header_line))
    for row in rows:
        line = "  ".join(cell(row[i] if i < len(row) else "", col_widths[i]) for i in range(len(headers)))
        print(line)


def print_json(data: Any) -> None:
    """Print data as JSON to stdout."""
    print(json.dumps(data, indent=2, default=str))


def emit(data: Any, *, format: str, headers: list[str] | None = None, rows: list[list[Any]] | None = None) -> None:
    """Emit output in requested format.

    For list/dict data use format='json'.
    For table use headers and rows.
    """
    if format == "json":
        if headers is not None and rows is not None:
            # Convert table to list of dicts
            out = [dict(zip(headers, row)) for row in rows]
            print_json(out)
        else:
            print_json(data)
    else:
        if headers and rows is not None:
            print_table(headers, rows)
        else:
            print_json(data)
