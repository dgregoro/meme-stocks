from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from backend.app.services.yahoo_service import PriceBar, YahooFinanceService
from backend.app.utils.errors import ExternalAPIError


class DummyTicker:
    def __init__(self, df: pd.DataFrame | Exception):
        self._df_or_exc = df

    def history(self, start: date, end: date) -> pd.DataFrame:
        if isinstance(self._df_or_exc, Exception):
            raise self._df_or_exc
        return self._df_or_exc


def test_yahoo_service_returns_empty_list_when_no_data(monkeypatch: pytest.MonkeyPatch) -> None:
    import yfinance as yf

    empty_df = pd.DataFrame()

    def fake_ticker(symbol: str) -> DummyTicker:
        return DummyTicker(empty_df)

    monkeypatch.setattr(yf, "Ticker", fake_ticker)  # type: ignore[arg-type]

    service = YahooFinanceService()
    prices = service.fetch_historical_prices("GME", start=date(2024, 1, 1), end=date(2024, 1, 2))

    assert prices == []


def test_yahoo_service_parses_valid_history(monkeypatch: pytest.MonkeyPatch) -> None:
    import yfinance as yf

    idx = pd.to_datetime(["2024-01-01"])
    df = pd.DataFrame(
        {
            "Open": [10.0],
            "High": [12.0],
            "Low": [9.5],
            "Close": [11.5],
            "Volume": [1000000],
        },
        index=idx,
    )

    def fake_ticker(symbol: str) -> DummyTicker:
        return DummyTicker(df)

    monkeypatch.setattr(yf, "Ticker", fake_ticker)  # type: ignore[arg-type]

    service = YahooFinanceService()
    prices = service.fetch_historical_prices("GME", start=date(2024, 1, 1), end=date(2024, 1, 2))

    assert len(prices) == 1
    bar = prices[0]
    assert isinstance(bar, PriceBar)
    assert bar.stock_symbol == "GME"
    assert bar.close == 11.5


def test_yahoo_service_raises_external_api_error_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import yfinance as yf

    def fake_ticker(symbol: str) -> DummyTicker:
        return DummyTicker(RuntimeError("network error"))

    monkeypatch.setattr(yf, "Ticker", fake_ticker)  # type: ignore[arg-type]

    service = YahooFinanceService()

    try:
        service.fetch_historical_prices("GME", start=date(2024, 1, 1), end=date(2024, 1, 2))
    except ExternalAPIError:
        # expected path
        return

    assert False, "Expected ExternalAPIError"
