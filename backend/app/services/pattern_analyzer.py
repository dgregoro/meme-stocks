from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from backend.app.config import get_settings
from backend.app.services.yahoo_service import PriceBar


@dataclass(frozen=True)
class PriceTrend:
    """Summary of price trend for a stock."""

    direction: str  # 'uptrend', 'downtrend', or 'sideways'
    sma_short: float | None
    sma_long: float | None
    rsi: float | None = None
    rsi_signal: str | None = None  # 'overbought', 'oversold', or 'neutral'


def relative_strength_index(values: list[float], period: int) -> float | None:
    """Compute RSI (Relative Strength Index) over the last `period` price changes.

    Returns None if insufficient data (len(values) < period + 1), invalid period, or empty.
    Uses standard formula: RSI = 100 - (100 / (1 + RS)), RS = avg_gain / avg_loss.
    avg_loss == 0 and avg_gain > 0 → 100; avg_loss == 0 and avg_gain == 0 → 50.
    Result clamped to [0, 100].
    """
    if not values or period <= 0 or len(values) < period + 1:
        return None
    changes: list[float] = []
    for i in range(1, len(values)):
        changes.append(values[i] - values[i - 1])
    recent = changes[-period:]
    gains = [c if c > 0 else 0.0 for c in recent]
    losses = [-c if c < 0 else 0.0 for c in recent]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        if avg_gain > 0:
            return 100.0
        return 50.0
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return max(0.0, min(100.0, rsi))


def simple_moving_average(values: List[float], window: int) -> float | None:
    """Compute SMA over the last `window` values. Returns None if insufficient data or invalid window."""
    if len(values) < window or window <= 0:
        return None
    subset = values[-window:]
    return sum(subset) / float(window)


def analyze_price_trend(
    bars: Iterable[PriceBar],
    short_window: int = 20,
    long_window: int = 50,
) -> PriceTrend:
    """Classify trend based on simple moving averages and RSI of close prices.

    - uptrend: sma_short > sma_long (may downgrade to sideways if volume confirmation fails)
    - downtrend: sma_short < sma_long
    - sideways: otherwise or insufficient data
    - rsi_signal: overbought/oversold/neutral from config thresholds
    """
    settings = get_settings()
    bar_list = list(bars)
    closes = [b.close for b in bar_list]
    if not closes:
        return PriceTrend(
            direction="sideways",
            sma_short=None,
            sma_long=None,
            rsi=None,
            rsi_signal=None,
        )

    sma_s = simple_moving_average(closes, short_window)
    sma_l = simple_moving_average(closes, long_window)
    rsi = relative_strength_index(closes, settings.rsi_period)

    if rsi is None:
        rsi_signal = None
    elif rsi >= settings.rsi_overbought:
        rsi_signal = "overbought"
    elif rsi <= settings.rsi_oversold:
        rsi_signal = "oversold"
    else:
        rsi_signal = "neutral"

    if sma_s is None or sma_l is None:
        return PriceTrend(
            direction="sideways",
            sma_short=sma_s,
            sma_long=sma_l,
            rsi=rsi,
            rsi_signal=rsi_signal,
        )

    if sma_s > sma_l:
        direction: str = "uptrend"
    elif sma_s < sma_l:
        direction = "downtrend"
    else:
        direction = "sideways"

    # Phase 2.4: treat weak-volume uptrend as sideways (no confirmed breakout)
    if direction == "uptrend" and settings.pattern_breakout_require_volume and len(bar_list) >= 2:
        prior = bar_list[:-1]
        last_bar = bar_list[-1]
        avg_vol = sum(b.volume for b in prior) / float(len(prior))
        if avg_vol > 0:
            vol_ratio = last_bar.volume / avg_vol
            if vol_ratio < settings.pattern_breakout_volume_ratio:
                direction = "sideways"

    return PriceTrend(
        direction=direction,
        sma_short=sma_s,
        sma_long=sma_l,
        rsi=rsi,
        rsi_signal=rsi_signal,
    )
