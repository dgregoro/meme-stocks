"""Tests for S&P 1500 research universe helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from backend.app.services.research_sp1500_universe_service import (
    fetch_sp_composite_1500_from_wikipedia,
    filter_sp1500_by_market_cap,
    load_constituents_csv,
    yahoo_ticker_symbol,
)


@pytest.mark.unit
def test_yahoo_ticker_symbol_class_share() -> None:
    assert yahoo_ticker_symbol("brk.b") == "BRK-B"


@pytest.mark.unit
def test_load_constituents_csv_header(tmp_path: Path) -> None:
    p = tmp_path / "t.csv"
    p.write_text("symbol\nAAA\nBBB\n", encoding="utf-8")
    assert load_constituents_csv(p) == ["AAA", "BBB"]


@pytest.mark.unit
def test_load_constituents_plain_lines(tmp_path: Path) -> None:
    p = tmp_path / "t.txt"
    p.write_text("XX\nYY\n", encoding="utf-8")
    assert load_constituents_csv(p) == ["XX", "YY"]


@pytest.mark.unit
def test_filter_sp1500_by_market_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    caps = {"A": 10e9, "B": 100e9, "C": None}

    def fake_mc(sym: str) -> float | None:
        return caps.get(sym)

    monkeypatch.setattr(
        "backend.app.services.research_sp1500_universe_service._market_cap_yahoo",
        fake_mc,
    )
    monkeypatch.setattr(
        "backend.app.services.research_sp1500_universe_service.time.sleep",
        lambda _: None,
    )

    r = filter_sp1500_by_market_cap(
        ["A", "B", "C"],
        max_market_cap_usd=50e9,
        as_of_label="2026-03-29",
        constituents_source="test",
        throttle_sec=0,
    )
    assert r.included == ["A"]
    assert len(r.excluded_over_cap) == 1 and r.excluded_over_cap[0]["symbol"] == "B"
    assert r.excluded_no_cap == ["C"]


@pytest.mark.unit
def test_fetch_sp_composite_1500_from_wikipedia_mocked() -> None:
    html = """
    <table>
      <tr><th>Symbol</th><th>Security</th></tr>
      <tr><td>AAA</td><td>Co A</td></tr>
      <tr><td>BBB</td><td>Co B</td></tr>
    </table>
    """

    def fake_get(url: str, **_kwargs: object) -> MagicMock:
        m = MagicMock()
        m.raise_for_status = MagicMock()
        m.text = html
        return m

    with patch("backend.app.services.research_sp1500_universe_service.requests.get", side_effect=fake_get):
        with patch(
            "backend.app.services.research_sp1500_universe_service.pd.read_html",
            return_value=[pd.DataFrame({"Symbol": ["AAA", "BBB"], "Security": ["Co A", "Co B"]})],
        ):
            out = fetch_sp_composite_1500_from_wikipedia(timeout_sec=1)
    assert out == ["AAA", "BBB"]


@pytest.mark.unit
def test_table_symbols_missing_column() -> None:
    from backend.app.services.research_sp1500_universe_service import _table_symbols

    df = pd.DataFrame({"Foo": [1]})
    with pytest.raises(ValueError, match="No Symbol"):
        _table_symbols(df)
