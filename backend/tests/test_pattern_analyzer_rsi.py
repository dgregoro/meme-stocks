"""Unit tests for RSI (Relative Strength Index) in pattern_analyzer."""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest

from backend.app.services.pattern_analyzer import (
    analyze_price_trend,
    relative_strength_index,
)
from backend.app.services.yahoo_service import PriceBar


# --- 4.1 Edge cases ---


@pytest.mark.unit
def test_rsi_empty_returns_none() -> None:
    assert relative_strength_index([], 14) is None


@pytest.mark.unit
def test_rsi_insufficient_length_returns_none() -> None:
    # need period + 1 = 15 values for period 14
    assert relative_strength_index([1.0, 2.0], 14) is None
    assert relative_strength_index(list(range(14)), 14) is None
    assert relative_strength_index(list(range(15)), 14) is not None


@pytest.mark.unit
def test_rsi_invalid_period_returns_none() -> None:
    assert relative_strength_index([1.0, 2.0, 3.0], 0) is None
    assert relative_strength_index([1.0, 2.0, 3.0], -1) is None


# --- 4.2 Known-behavior cases ---


@pytest.mark.unit
def test_rsi_strictly_increasing_avg_loss_zero_returns_100() -> None:
    # 15 closes: each +1 → 14 gains, 0 losses → avg_loss=0, avg_gain>0 → 100
    values = [float(i) for i in range(15)]
    assert relative_strength_index(values, 14) == 100.0


@pytest.mark.unit
def test_rsi_strictly_decreasing_avg_gain_zero_returns_0() -> None:
    # 15 closes: each -1 → 0 gains, 14 losses → avg_gain=0 → RSI = 0
    values = [float(100 - i) for i in range(15)]
    assert relative_strength_index(values, 14) == 0.0


@pytest.mark.unit
def test_rsi_flat_returns_50() -> None:
    values = [10.0] * 15
    assert relative_strength_index(values, 14) == 50.0


@pytest.mark.unit
def test_rsi_clamped_to_0_100() -> None:
    # Defensive: result should always be in [0, 100]
    values = [float(i) for i in range(20)]
    rsi = relative_strength_index(values, 14)
    assert rsi is not None
    assert 0 <= rsi <= 100


# --- 4.3 analyze_price_trend integration ---


def _make_bar(symbol: str, d: date, close: float) -> PriceBar:
    return PriceBar(
        stock_symbol=symbol,
        date=d,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1000,
        source_timestamp=datetime.now(timezone.utc),
    )


@pytest.mark.unit
def test_analyze_price_trend_returns_rsi_when_enough_bars() -> None:
    # 20 bars so SMA 20/50: sma_long will be None (need 50). But RSI needs period+1=15.
    bars = [_make_bar("GME", date(2024, 1, 1), close=100.0 + i) for i in range(25)]
    with patch("backend.app.services.pattern_analyzer.get_settings") as mock:
        mock.return_value.rsi_period = 14
        mock.return_value.rsi_overbought = 70.0
        mock.return_value.rsi_oversold = 30.0
        trend = analyze_price_trend(bars)
    assert trend.rsi is not None
    assert 0 <= trend.rsi <= 100
    # Increasing prices → high RSI → overbought
    assert trend.rsi_signal == "overbought"


@pytest.mark.unit
def test_analyze_price_trend_rsi_signal_oversold() -> None:
    bars = [_make_bar("GME", date(2024, 1, 1), close=100.0 - i) for i in range(25)]
    with patch("backend.app.services.pattern_analyzer.get_settings") as mock:
        mock.return_value.rsi_period = 14
        mock.return_value.rsi_overbought = 70.0
        mock.return_value.rsi_oversold = 30.0
        trend = analyze_price_trend(bars)
    assert trend.rsi is not None
    assert trend.rsi_signal == "oversold"


@pytest.mark.unit
def test_analyze_price_trend_rsi_signal_neutral() -> None:
    # Flat then small move: RSI near 50
    bars = [_make_bar("GME", date(2024, 1, 1), close=50.0) for _ in range(20)]
    with patch("backend.app.services.pattern_analyzer.get_settings") as mock:
        mock.return_value.rsi_period = 14
        mock.return_value.rsi_overbought = 70.0
        mock.return_value.rsi_oversold = 30.0
        trend = analyze_price_trend(bars)
    assert trend.rsi == 50.0
    assert trend.rsi_signal == "neutral"


@pytest.mark.unit
def test_analyze_price_trend_insufficient_sma_returns_complete_price_trend() -> None:
    """SMA-insufficient path: ~15 bars enough for RSI but not for SMA 20/50; no exception, full PriceTrend."""
    bars = [_make_bar("GME", date(2024, 1, 1), close=100.0 + i) for i in range(15)]
    with patch("backend.app.services.pattern_analyzer.get_settings") as mock:
        mock.return_value.rsi_period = 14
        mock.return_value.rsi_overbought = 70.0
        mock.return_value.rsi_oversold = 30.0
        trend = analyze_price_trend(bars)
    assert trend.direction == "sideways"
    assert trend.sma_short is None
    assert trend.sma_long is None
    assert trend.rsi is not None
    assert trend.rsi_signal in {"overbought", "oversold", "neutral"}
