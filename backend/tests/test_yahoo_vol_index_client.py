"""Tests for Yahoo VIX/VIX3M client (alignment, no network)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

from backend.app.clients.yahoo_vol_index_client import YahooVolIndexClient


@pytest.mark.unit
def test_fetch_vix_vix3m_closes_aligns_mismatched_index_timezones(monkeypatch: pytest.MonkeyPatch) -> None:
    """^VIX and ^VIX3M often return different tz-aware DatetimeIndexes; we join on calendar date."""
    call_count = {"n": 0}

    def fake_history(_ticker: object, start: date, end: date) -> pd.DataFrame:
        call_count["n"] += 1
        d0 = date(2024, 1, 2)
        idx = [d0, d0 + timedelta(days=1)]
        if call_count["n"] == 1:
            ts_idx = pd.DatetimeIndex(
                [datetime(d.year, d.month, d.day, tzinfo=timezone(timedelta(hours=-6))) for d in idx]
            )
            close = [18.0, 19.0]
        else:
            ts_idx = pd.DatetimeIndex(
                [datetime(d.year, d.month, d.day, tzinfo=timezone(timedelta(hours=-5))) for d in idx]
            )
            close = [20.0, 21.0]
        return pd.DataFrame({"Close": close}, index=ts_idx)

    monkeypatch.setattr(YahooVolIndexClient, "_history_frame", staticmethod(fake_history))
    cli = YahooVolIndexClient()
    rows = cli.fetch_vix_vix3m_closes(
        date(2024, 1, 1),
        date(2024, 1, 10),
        vix_symbol="^VIX",
        vix3m_symbol="^VIX3M",
    )

    assert len(rows) == 2
    assert rows[0] == (date(2024, 1, 2), 18.0, 20.0)
    assert rows[1] == (date(2024, 1, 3), 19.0, 21.0)
