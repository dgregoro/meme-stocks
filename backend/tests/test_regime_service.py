"""Unit tests for pure regime helpers (014)."""

from __future__ import annotations

import pytest

from backend.app.services.regime_service import get_market_trend, get_volatility, is_regime_ok


@pytest.mark.unit
def test_get_market_trend_passes_above_ma() -> None:
    # window=2: prior 100,100 then today 101 -> above SMA 100
    assert get_market_trend([100.0, 100.0, 101.0], 2) is True


@pytest.mark.unit
def test_get_market_trend_fails_below_ma() -> None:
    assert get_market_trend([100.0, 100.0, 90.0], 2) is False


@pytest.mark.unit
def test_get_volatility_low_on_flat_series() -> None:
    assert get_volatility([100.0, 100.0, 100.0], 2) == pytest.approx(0.0)


@pytest.mark.unit
def test_get_volatility_high_on_swingy_series() -> None:
    v = get_volatility([100.0, 110.0, 80.0], 2)
    assert v > 0.1


@pytest.mark.unit
def test_is_regime_ok_combines_trend_and_vol() -> None:
    flat = [100.0, 100.0, 101.0]
    assert (
        is_regime_ok(
            closes_for_trend=flat,
            market_trend_window=2,
            require_market_uptrend=True,
            closes_for_vol=flat,
            volatility_window=2,
            volatility_threshold=0.05,
            require_low_volatility=True,
        )
        is True
    )
    swing = [100.0, 110.0, 80.0]
    assert (
        is_regime_ok(
            closes_for_trend=[100.0, 100.0, 105.0],
            market_trend_window=2,
            require_market_uptrend=True,
            closes_for_vol=swing,
            volatility_window=2,
            volatility_threshold=0.01,
            require_low_volatility=True,
        )
        is False
    )
