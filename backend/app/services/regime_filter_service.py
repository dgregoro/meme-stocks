"""Market regime gate for paper trading: benchmark trend + optional volatility (014)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.services.regime_service import get_market_trend, get_volatility

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegimeFilterParams:
    """Bundled regime inputs (avoids circular imports with PaperTradingConfig)."""

    enabled: bool
    regime_benchmark_symbol: str
    market_trend_window: int
    require_market_uptrend: bool
    volatility_window: int
    volatility_threshold: float
    require_low_volatility: bool
    regime_sector_strength_required: bool


def evaluate_regime_filter(
    price_repo: PriceDataRepository,
    decision_date: date,
    params: RegimeFilterParams,
    *,
    sector_confirmation_passed: bool | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Return (allow_trade, snapshot).

    When ``enabled`` is false, returns (True, {}).
    When enabled, missing benchmark data or insufficient history → fail (do not trade).
    If ``regime_sector_strength_required``, ``sector_confirmation_passed`` must be True.
    """
    if not params.enabled:
        return True, {}

    bench = params.regime_benchmark_symbol.strip().upper()
    if not bench:
        logger.info("Regime gate skip: empty benchmark symbol")
        return False, {"regime_filter_passed": False, "regime_skip_reason": "empty_benchmark"}

    if params.regime_sector_strength_required and sector_confirmation_passed is not True:
        logger.info(
            "Regime gate skip: regime_sector_strength_required but sector_confirmation_passed=%r",
            sector_confirmation_passed,
        )
        return False, {
            "regime_benchmark_symbol": bench,
            "regime_decision_date": decision_date,
            "regime_filter_passed": False,
            "regime_skip_reason": "sector_strength_required_not_met",
            "regime_sector_strength_passed": False,
        }

    dates = price_repo.list_dates_for_symbol(bench)
    try:
        i = dates.index(decision_date)
    except ValueError:
        logger.info("Regime gate skip: no benchmark bar for %s on %s", bench, decision_date)
        return False, {
            "regime_benchmark_symbol": bench,
            "regime_decision_date": decision_date,
            "regime_filter_passed": False,
            "regime_skip_reason": "missing_benchmark_bar",
        }

    bar_asof = price_repo.get_for_date(bench, decision_date)
    if bar_asof is None or float(bar_asof.close) <= 0:
        return False, {
            "regime_benchmark_symbol": bench,
            "regime_decision_date": decision_date,
            "regime_filter_passed": False,
            "regime_skip_reason": "missing_benchmark_close",
        }
    close_today = float(bar_asof.close)

    snap: dict[str, Any] = {
        "regime_benchmark_symbol": bench,
        "regime_decision_date": decision_date,
        "regime_benchmark_close": close_today,
        "regime_benchmark_ma": None,
        "regime_market_uptrend_passed": None,
        "regime_volatility": None,
        "regime_low_volatility_passed": None,
        "regime_sector_strength_passed": True if params.regime_sector_strength_required else None,
        "regime_filter_passed": True,
    }

    uptrend_ok = True
    if params.require_market_uptrend:
        w_m = params.market_trend_window
        if w_m < 1:
            return False, {**snap, "regime_filter_passed": False, "regime_skip_reason": "invalid_trend_window"}
        if i < w_m:
            logger.info("Regime gate skip: insufficient history for MA (%s window=%s)", bench, w_m)
            return False, {
                **snap,
                "regime_filter_passed": False,
                "regime_skip_reason": "insufficient_history_ma",
            }
        prior: list[float] = []
        for j in range(i - w_m, i):
            b = price_repo.get_for_date(bench, dates[j])
            if b is None or float(b.close) <= 0:
                return False, {
                    **snap,
                    "regime_filter_passed": False,
                    "regime_skip_reason": "missing_benchmark_history_ma",
                }
            prior.append(float(b.close))
        try:
            uptrend_ok = get_market_trend(prior + [close_today], w_m)
        except ValueError:
            return False, {**snap, "regime_filter_passed": False, "regime_skip_reason": "invalid_trend_inputs"}
        ma_val = sum(prior) / len(prior)
        snap["regime_benchmark_ma"] = ma_val
        snap["regime_market_uptrend_passed"] = uptrend_ok

    vol_ok = True
    if params.require_low_volatility:
        w_v = params.volatility_window
        if w_v < 2:
            return False, {**snap, "regime_filter_passed": False, "regime_skip_reason": "invalid_vol_window"}
        need = w_v + 1
        if i < need - 1:
            logger.info("Regime gate skip: insufficient history for vol (%s window=%s)", bench, w_v)
            return False, {
                **snap,
                "regime_filter_passed": False,
                "regime_skip_reason": "insufficient_history_vol",
            }
        closes: list[float] = []
        start_idx = i - w_v
        for j in range(start_idx, i + 1):
            b = price_repo.get_for_date(bench, dates[j])
            if b is None or float(b.close) <= 0:
                return False, {
                    **snap,
                    "regime_filter_passed": False,
                    "regime_skip_reason": "missing_benchmark_history_vol",
                }
            closes.append(float(b.close))
        try:
            vol = get_volatility(closes, w_v)
        except ValueError:
            return False, {
                **snap,
                "regime_filter_passed": False,
                "regime_skip_reason": "invalid_return_vol",
            }
        vol_ok = vol <= params.volatility_threshold
        snap["regime_volatility"] = vol
        snap["regime_low_volatility_passed"] = vol_ok

    allowed = uptrend_ok and vol_ok
    snap["regime_filter_passed"] = allowed
    if not allowed:
        snap["regime_skip_reason"] = "regime_conditions_failed"
    return allowed, snap
