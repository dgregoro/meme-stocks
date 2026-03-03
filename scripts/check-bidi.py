#!/usr/bin/env python3
"""Scan tracked files for bidirectional / hidden Unicode control characters.

Fails if any are found. Run from repo root.
See: https://unicode.org/reports/tr9/ and GitHub's bidi warning.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Bidirectional and embedding control characters (U+202A–U+202E, U+2066–U+2069, U+200E, U+200F)
BIDI_CHARS = (
    "\u202A"  # LEFT-TO-RIGHT EMBEDDING
    "\u202B"  # RIGHT-TO-LEFT EMBEDDING
    "\u202D"  # LEFT-TO-RIGHT OVERRIDE
    "\u202E"  # RIGHT-TO-LEFT OVERRIDE
    "\u202C"  # POP DIRECTIONAL FORMATTING
    "\u2066"  # LEFT-TO-RIGHT ISOLATE
    "\u2067"  # RIGHT-TO-LEFT ISOLATE
    "\u2068"  # FIRST STRONG ISOLATE
    "\u2069"  # POP DIRECTIONAL ISOLATE
    "\u200E"  # LEFT-TO-RIGHT MARK
    "\u200F"  # RIGHT-TO-LEFT MARK
)
BIDI_SET = frozenset(BIDI_CHARS)


def check_file(path: Path) -> list[tuple[int, str]]:
    """Return list of (line_num, line) where line contains bidi chars."""
    found: list[tuple[int, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return found
    for i, line in enumerate(text.splitlines(), start=1):
        if any(c in BIDI_SET for c in line):
            found.append((i, line))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="Check for bidi Unicode in source files")
    parser.add_argument("paths", nargs="*", help="Paths to scan (default: backend/ frontend/)")
    args = parser.parse_args()
    roots = args.paths or ["backend/", "frontend/"]
    repo = Path.cwd()
    if not (repo / "backend").exists():
        sys.stderr.write("Run from repo root.\n")
        return 2
    ext_allow = {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".yml", ".yaml", ".md", ".txt", ".html"}
    skip_dirs = {"node_modules", "__pycache__", ".git", "dist", "build", ".venv", "venv"}
    found_any = False
    for root in roots:
        rpath = Path(root)
        for f in rpath.rglob("*") if rpath.is_dir() else [rpath]:
            if not f.is_file():
                continue
            if any(part in skip_dirs for part in f.parts):
                continue
            if f.suffix not in ext_allow and f.name not in (
                "Dockerfile",
                "Containerfile",
                "Makefile",
            ):
                continue
            hits = check_file(f)
            if hits:
                found_any = True
                rel = f.relative_to(repo) if repo in f.parents else f
                for ln, content in hits:
                    sys.stderr.write(f"{rel}:{ln}: bidi/hidden unicode in: {repr(content[:80])}\n")
    return 1 if found_any else 0


if __name__ == "__main__":
    sys.exit(main())
