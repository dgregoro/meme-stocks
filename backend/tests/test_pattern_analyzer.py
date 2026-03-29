from __future__ import annotations

from datetime import date, datetime, timezone

from unittest.mock import patch

import pytest

from backend.app.services.pattern_analyzer import PriceTrend, analyze_price_trend
from backend.app.services.yahoo_service import PriceBar


def make_bar(symbol: str, d: date, close: float, *, volume: int = 1000) -> PriceBar:
    return PriceBar(
        stock_symbol=symbol,
        date=d,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=volume,
        source_timestamp=datetime.now(timezone.utc),
    )


def test_analyze_price_trend_no_data_is_sideways() -> None:
    trend = analyze_price_trend([])
    assert isinstance(trend, PriceTrend)
    assert trend.direction == "sideways"
    assert trend.sma_short is None
    assert trend.sma_long is None
    assert trend.rsi is None
    assert trend.rsi_signal is None


def test_analyze_price_trend_uptrend_when_short_sma_above_long() -> None:
    # Use a simple sequence of days without worrying about month lengths.
    bars = [make_bar("GME", date(2024, 1, 1), close=10 + i) for i in range(60)]
    trend = analyze_price_trend(bars)
    assert trend.direction == "uptrend"
    assert trend.sma_short is not None
    assert trend.sma_long is not None
    assert trend.sma_short > trend.sma_long


def test_analyze_price_trend_downtrend_when_short_sma_below_long() -> None:
    bars = [make_bar("GME", date(2024, 1, 1), close=100 - i) for i in range(60)]
    trend = analyze_price_trend(bars)
    assert trend.direction == "downtrend"
    assert trend.sma_short is not None
    assert trend.sma_long is not None
    assert trend.sma_short < trend.sma_long


@pytest.mark.unit
def test_analyze_price_trend_weak_volume_downgrades_uptrend_to_sideways() -> None:
    bars = [make_bar("GME", date(2024, 1, 1), close=10 + i, volume=10_000) for i in range(59)]
    bars.append(make_bar("GME", date(2024, 3, 1), close=10 + 59, volume=100))  # last day: thin volume vs average
    with patch("backend.app.services.pattern_analyzer.get_settings") as mock:
        mock.return_value.rsi_period = 14
        mock.return_value.rsi_overbought = 70.0
        mock.return_value.rsi_oversold = 30.0
        mock.return_value.pattern_breakout_require_volume = True
        mock.return_value.pattern_breakout_volume_ratio = 1.5
        trend = analyze_price_trend(bars)
    assert trend.sma_short is not None and trend.sma_long is not None
    assert trend.sma_short > trend.sma_long
    assert trend.direction == "sideways"
