from __future__ import annotations

from datetime import date, datetime

from backend.app.services.pattern_analyzer import PriceTrend, analyze_price_trend
from backend.app.services.yahoo_service import PriceBar


def make_bar(symbol: str, d: date, close: float) -> PriceBar:
    return PriceBar(
        stock_symbol=symbol,
        date=d,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1000,
        source_timestamp=datetime.utcnow(),
    )


def test_analyze_price_trend_no_data_is_sideways() -> None:
    trend = analyze_price_trend([])
    assert isinstance(trend, PriceTrend)
    assert trend.direction == "sideways"
    assert trend.sma_short is None
    assert trend.sma_long is None


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


