from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from backend.app.services.yahoo_service import PriceBar


@dataclass(frozen=True)
class PriceTrend:
    """Summary of price trend for a stock."""

    direction: str  # 'uptrend', 'downtrend', or 'sideways'
    sma_short: float | None
    sma_long: float | None


def simple_moving_average(values: List[float], window: int) -> float | None:
    if len(values) < window or window <= 0:
        return None
    subset = values[-window:]
    return sum(subset) / float(window)


def analyze_price_trend(
    bars: Iterable[PriceBar], short_window: int = 20, long_window: int = 50
) -> PriceTrend:
    """Classify trend based on simple moving averages of close prices.

    - uptrend: sma_short > sma_long
    - downtrend: sma_short < sma_long
    - sideways: otherwise or insufficient data
    """

    closes = [b.close for b in bars]
    if not closes:
        return PriceTrend(direction="sideways", sma_short=None, sma_long=None)

    sma_s = simple_moving_average(closes, short_window)
    sma_l = simple_moving_average(closes, long_window)

    if sma_s is None or sma_l is None:
        return PriceTrend(direction="sideways", sma_short=sma_s, sma_long=sma_l)

    if sma_s > sma_l:
        direction = "uptrend"
    elif sma_s < sma_l:
        direction = "downtrend"
    else:
        direction = "sideways"

    return PriceTrend(direction=direction, sma_short=sma_s, sma_long=sma_l)
