"""Sector ETF trend / momentum gate for paper trading (explainable daily rules only)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.data.stock_sector_etf_map import resolve_sector_etf

logger = logging.getLogger(__name__)

SectorTrendMethod = Literal["ma_above", "rolling_return", "combined"]


@dataclass(frozen=True)
class SectorConfirmationParams:
    """Input bundle to avoid importing PaperTradingConfig (prevents circular imports)."""

    enabled: bool
    sector_etf_symbol: str | None
    sector_trend_method: SectorTrendMethod
    sector_trend_window: int
    minimum_sector_return_pct: float
    require_positive_trend: bool


def evaluate_sector_confirmation(
    price_repo: PriceDataRepository,
    leader_symbol: str,
    as_of_date: date,
    params: SectorConfirmationParams,
) -> tuple[bool, dict[str, Any]]:
    """Return (allow_trade, snapshot).

    When ``enabled`` is false, returns (True, {}).
    Unmapped leader (no override): pass with warning and snapshot with null ETF.
    Missing ETF history or bar on as_of: fail (do not trade).
    """
    if not params.enabled:
        return True, {}

    etf = resolve_sector_etf(leader_symbol, params.sector_etf_symbol)
    if etf is None:
        logger.warning(
            "Sector confirmation enabled but no ETF mapping for leader %s (override=%r); allowing trade",
            leader_symbol,
            params.sector_etf_symbol,
        )
        return True, {
            "sector_etf_symbol": None,
            "sector_close": None,
            "sector_ma": None,
            "sector_rolling_return_pct": None,
            "sector_confirmation_passed": True,
        }

    etf_dates = price_repo.list_dates_for_symbol(etf)
    try:
        i = etf_dates.index(as_of_date)
    except ValueError:
        logger.info(
            "Sector gate skip: no ETF bar for %s on %s",
            etf,
            as_of_date,
        )
        return False, {
            "sector_etf_symbol": etf,
            "sector_close": None,
            "sector_ma": None,
            "sector_rolling_return_pct": None,
            "sector_confirmation_passed": False,
            "sector_skip_reason": "missing_etf_bar_on_entry_date",
        }

    w = params.sector_trend_window
    if w < 1:
        return False, {
            "sector_etf_symbol": etf,
            "sector_confirmation_passed": False,
            "sector_skip_reason": "invalid_sector_trend_window",
        }

    bar_asof = price_repo.get_for_date(etf, as_of_date)
    if bar_asof is None or float(bar_asof.close) <= 0:
        return False, {
            "sector_etf_symbol": etf,
            "sector_confirmation_passed": False,
            "sector_skip_reason": "missing_etf_close",
        }
    close_today = float(bar_asof.close)

    def _prior_closes(count: int) -> list[float] | None:
        if i < count:
            return None
        out: list[float] = []
        for j in range(i - count, i):
            bar = price_repo.get_for_date(etf, etf_dates[j])
            if bar is None or float(bar.close) <= 0:
                return None
            out.append(float(bar.close))
        return out

    method = params.sector_trend_method
    ma_val: float | None = None
    roll_ret: float | None = None
    ok_ma = True
    ok_ret = True

    if method in ("ma_above", "combined"):
        prior = _prior_closes(w)
        if prior is None:
            logger.info("Sector gate skip: insufficient history for MA (%s window=%s)", etf, w)
            return False, {
                "sector_etf_symbol": etf,
                "sector_close": close_today,
                "sector_ma": None,
                "sector_rolling_return_pct": None,
                "sector_confirmation_passed": False,
                "sector_skip_reason": "insufficient_etf_history_ma",
            }
        ma_val = sum(prior) / len(prior)
        if params.require_positive_trend:
            ok_ma = close_today > ma_val
        else:
            ok_ma = close_today >= ma_val

    if method in ("rolling_return", "combined"):
        if i < w:
            logger.info("Sector gate skip: insufficient history for return (%s window=%s)", etf, w)
            return False, {
                "sector_etf_symbol": etf,
                "sector_close": close_today,
                "sector_ma": ma_val,
                "sector_rolling_return_pct": None,
                "sector_confirmation_passed": False,
                "sector_skip_reason": "insufficient_etf_history_return",
            }
        bar_start = price_repo.get_for_date(etf, etf_dates[i - w])
        if bar_start is None or float(bar_start.close) <= 0:
            return False, {
                "sector_etf_symbol": etf,
                "sector_close": close_today,
                "sector_ma": ma_val,
                "sector_rolling_return_pct": None,
                "sector_confirmation_passed": False,
                "sector_skip_reason": "missing_etf_bar_return_start",
            }
        roll_ret = (close_today / float(bar_start.close) - 1.0) * 100.0
        ok_ret = roll_ret >= params.minimum_sector_return_pct
        if params.require_positive_trend and params.minimum_sector_return_pct <= 0:
            ok_ret = ok_ret and roll_ret > 0.0

    if method == "ma_above":
        passed = ok_ma
    elif method == "rolling_return":
        passed = ok_ret
    elif method == "combined":
        passed = ok_ma and ok_ret
    else:
        return False, {
            "sector_etf_symbol": etf,
            "sector_close": close_today,
            "sector_ma": ma_val,
            "sector_rolling_return_pct": roll_ret,
            "sector_confirmation_passed": False,
            "sector_skip_reason": "invalid_sector_trend_method",
        }

    snap: dict[str, Any] = {
        "sector_etf_symbol": etf,
        "sector_close": close_today,
        "sector_ma": ma_val,
        "sector_rolling_return_pct": roll_ret,
        "sector_confirmation_passed": passed,
    }
    if not passed:
        snap["sector_skip_reason"] = "sector_trend_not_met"
    return passed, snap
