"""Shared portfolio metrics for research backtests (simple equity series)."""

from __future__ import annotations


def max_drawdown_from_equity(equities: list[float]) -> float:
    """Return max peak-to-trough drawdown as a positive percentage of peak (0–100 scale)."""
    if not equities:
        return 0.0
    peak = equities[0]
    max_dd = 0.0
    for eq in equities:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100.0 if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd


def compound_equity_from_period_returns(returns_fraction: list[float]) -> list[float]:
    """Return equity curve starting at 1.0; each input is simple return for the period (e.g. 0.01 = +1%)."""
    if not returns_fraction:
        return [1.0]
    eq: list[float] = [1.0]
    for r in returns_fraction:
        eq.append(eq[-1] * (1.0 + r))
    return eq
