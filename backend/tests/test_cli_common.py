"""Tests for shared CLI helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.cli.common import load_symbols_from_path


@pytest.mark.unit
def test_load_symbols_from_path_one_per_line(tmp_path: Path) -> None:
    p = tmp_path / "s.txt"
    p.write_text("aaa\nBBB\n# skip\nCCC,\n", encoding="utf-8")
    assert load_symbols_from_path(p) == ["AAA", "BBB", "CCC"]


@pytest.mark.unit
def test_load_symbols_from_path_comma_line(tmp_path: Path) -> None:
    p = tmp_path / "s.txt"
    p.write_text("X,Y\nZ\n", encoding="utf-8")
    assert load_symbols_from_path(p) == ["X", "Y", "Z"]


@pytest.mark.unit
def test_load_symbols_skips_symbol_header(tmp_path: Path) -> None:
    p = tmp_path / "s.txt"
    p.write_text("symbol\nSPY\n", encoding="utf-8")
    assert load_symbols_from_path(p) == ["SPY"]
