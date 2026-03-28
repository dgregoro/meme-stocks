"""Pure market-regime helpers (014). Used by ``regime_filter_service`` with ``PriceDataRepository``."""

from __future__ import annotations

import statistics


def get_market_trend(closes: list[float], window: int) -> bool:
    """Return True when the latest close is above the SMA of the prior ``window`` closes.

    ``closes`` must be oldest-to-newest and have length ``window + 1`` (``window`` history
    bars before decision, then decision-day close as the last element). Matches paper
    trading: uptrend iff close_today > mean(prior ``window`` closes).
    """
    if window < 1:
        raise ValueError("market_trend_window must be >= 1")
    if len(closes) != window + 1:
        raise ValueError(f"expected {window + 1} closes for trend (window prior + today), got {len(closes)}")
    close_today = closes[-1]
    ma = sum(closes[:-1]) / window
    return close_today > ma


def get_volatility(closes: list[float], window: int) -> float:
    """Population std of simple daily returns over the last ``window`` returns.

    ``closes`` is oldest-to-newest with length ``window + 1`` (same convention as
    ``regime_filter_service``). Requires ``window >= 2``.
    """
    if window < 2:
        raise ValueError("volatility_window must be >= 2")
    if len(closes) != window + 1:
        raise ValueError(f"expected {window + 1} closes for volatility, got {len(closes)}")
    rets: list[float] = []
    for k in range(1, len(closes)):
        p0, p1 = closes[k - 1], closes[k]
        if p0 <= 0:
            raise ValueError("non-positive prior close for return")
        rets.append(p1 / p0 - 1.0)
    return statistics.pstdev(rets) if len(rets) > 1 else 0.0


def is_regime_ok(
    *,
    closes_for_trend: list[float] | None,
    market_trend_window: int,
    require_market_uptrend: bool,
    closes_for_vol: list[float] | None,
    volatility_window: int,
    volatility_threshold: float,
    require_low_volatility: bool,
) -> bool:
    """Combined gate: optional uptrend AND optional low-vol (each clause can be disabled)."""
    uptrend = True
    if require_market_uptrend:
        if closes_for_trend is None:
            raise ValueError("closes_for_trend required when require_market_uptrend is true")
        uptrend = get_market_trend(closes_for_trend, market_trend_window)
    low_vol = True
    if require_low_volatility:
        if closes_for_vol is None:
            raise ValueError("closes_for_vol required when require_low_volatility is true")
        vol = get_volatility(closes_for_vol, volatility_window)
        low_vol = vol <= volatility_threshold
    return uptrend and low_vol
