"""Long-only daily bar backtest: discrete signals → trades → gross/net returns.

**Percent space (reporting):** trade metrics and :func:`daily_simple_result_to_jsonable`
use **percentage points** (e.g. ``21.0`` meaning +21% simple return), aligned with
``apply_round_trip_cost`` and ``net-metrics-reporting.md``.

**Fractions (internal only):** ``DailySimpleBacktestResult.period_returns_*`` are
simple-return **fractions** for :func:`compound_equity_from_period_returns`.

See specs/020-shared-research-execution/daily-simple-backtest.md.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Mapping

from backend.app.services.research_execution.costs import (
    apply_round_trip_cost,
    round_trip_cost_pct_from_bps,
)
from backend.app.services.research_execution.metrics import (
    compound_equity_from_period_returns,
    max_drawdown_from_equity,
)

logger = logging.getLogger(__name__)

EntryMode = Literal["same_close", "next_open"]


@dataclass
class _OpenLong:
    entry_px: float
    exit_idx: int
    entry_date: date


@dataclass(frozen=True)
class DailyBar:
    """One regular-session daily OHLCV bar."""

    d: date
    open: float
    high: float
    low: float
    close: float


@dataclass
class DailySimpleBacktestConfig:
    """Execution assumptions (long-only MVP)."""

    entry: EntryMode = "next_open"
    horizon_days: int = 2
    round_trip_cost_bps: float = 0.0


@dataclass
class DailySimpleTrade:
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    trade_return_pct_gross: float
    trade_return_pct_net: float


@dataclass
class DailySimpleSkip:
    """Structured skip when a trade cannot be completed (missing bar, range, etc.)."""

    reason: str
    signal_date: date | None
    detail: str


@dataclass
class DailySimpleBacktestResult:
    trades: list[DailySimpleTrade] = field(default_factory=list)
    skips: list[DailySimpleSkip] = field(default_factory=list)
    #: Per-trade simple returns as **fractions** (for compounding only).
    period_returns_gross: list[float] = field(default_factory=list)
    #: Per-trade simple returns as **fractions** (for compounding only).
    period_returns_net: list[float] = field(default_factory=list)
    #: Equity index starting at 1.0 (not percent).
    equity_gross: list[float] = field(default_factory=list)
    equity_net: list[float] = field(default_factory=list)
    #: Max peak-to-trough drawdown as **percentage points** of peak (0–100 scale).
    max_drawdown_pct_gross: float = 0.0
    max_drawdown_pct_net: float = 0.0
    cost_round_trip_bps: float = 0.0
    cost_model: str = "fixed_round_trip_bps"


def run_daily_simple_long_only_backtest(
    bars: list[DailyBar],
    signals: Mapping[date, int],
    config: DailySimpleBacktestConfig | None = None,
) -> DailySimpleBacktestResult:
    """Run a long-only backtest on sorted unique trading days.

    * ``signals[d] == 1`` requests a new entry when flat (no overlapping positions).
    * ``next_open``: signal on day *i* → fill at open of bar *i+1*.
    * ``same_close``: signal on day *i* → fill at close of bar *i*.
    * Exit at **close** of bar index ``entry_idx + horizon_days - 1``.

    Missing future bars needed for next_open or exit → skip with :class:`DailySimpleSkip`;
    reasons are logged at INFO.
    """
    cfg = config or DailySimpleBacktestConfig()
    if cfg.horizon_days < 1:
        raise ValueError("horizon_days must be >= 1")
    if not bars:
        return DailySimpleBacktestResult(
            cost_round_trip_bps=cfg.round_trip_cost_bps,
            cost_model="fixed_round_trip_bps",
        )

    for a, b in zip(bars, bars[1:]):
        if a.d >= b.d:
            raise ValueError("bars must be sorted by date with unique days")

    result = DailySimpleBacktestResult(
        cost_round_trip_bps=cfg.round_trip_cost_bps,
        cost_model="fixed_round_trip_bps",
    )
    holding: _OpenLong | None = None
    pending_entry_idx: int | None = None
    cost_pct = round_trip_cost_pct_from_bps(cfg.round_trip_cost_bps)

    n = len(bars)

    def record_skip(reason: str, signal_date: date | None, detail: str) -> None:
        result.skips.append(DailySimpleSkip(reason=reason, signal_date=signal_date, detail=detail))
        logger.info("daily_simple_backtest skip: %s (%s)", reason, detail)

    for i, bar in enumerate(bars):
        if holding is not None and i == holding.exit_idx:
            exit_px = float(bar.close)
            entry_px = holding.entry_px
            entry_date = holding.entry_date
            gross_pct = (exit_px - entry_px) / entry_px * 100.0 if entry_px else 0.0
            net_pct = apply_round_trip_cost(gross_pct, cost_pct)
            result.trades.append(
                DailySimpleTrade(
                    entry_date=entry_date,
                    exit_date=bar.d,
                    entry_price=entry_px,
                    exit_price=exit_px,
                    trade_return_pct_gross=gross_pct,
                    trade_return_pct_net=net_pct,
                )
            )
            result.period_returns_gross.append(gross_pct / 100.0)
            result.period_returns_net.append(net_pct / 100.0)
            holding = None

        if pending_entry_idx is not None and i == pending_entry_idx:
            entry_px = float(bar.open)
            exit_idx = i + cfg.horizon_days - 1
            if exit_idx >= n:
                record_skip(
                    "insufficient_bars_for_exit",
                    bar.d,
                    f"need exit_idx={exit_idx} have n={n}",
                )
                pending_entry_idx = None
                continue
            holding = _OpenLong(entry_px=entry_px, exit_idx=exit_idx, entry_date=bar.d)
            pending_entry_idx = None

        if holding is not None or pending_entry_idx is not None:
            continue

        if int(signals.get(bar.d, 0)) != 1:
            continue

        if cfg.entry == "same_close":
            entry_px = float(bar.close)
            exit_idx = i + cfg.horizon_days - 1
            if exit_idx >= n:
                record_skip(
                    "insufficient_bars_for_exit",
                    bar.d,
                    f"same_close exit_idx={exit_idx} n={n}",
                )
                continue
            holding = _OpenLong(entry_px=entry_px, exit_idx=exit_idx, entry_date=bar.d)
        else:
            if i + 1 >= n:
                record_skip(
                    "missing_next_bar",
                    bar.d,
                    "next_open requires bar after signal day",
                )
                continue
            pending_entry_idx = i + 1

    if result.period_returns_gross:
        result.equity_gross = compound_equity_from_period_returns(result.period_returns_gross)
        result.equity_net = compound_equity_from_period_returns(result.period_returns_net)
        result.max_drawdown_pct_gross = max_drawdown_from_equity(result.equity_gross)
        result.max_drawdown_pct_net = max_drawdown_from_equity(result.equity_net)
    else:
        result.equity_gross = [1.0]
        result.equity_net = [1.0]

    return result


def daily_simple_result_to_jsonable(res: DailySimpleBacktestResult) -> dict:
    """Build a JSON-serializable dict using **percentage points** for all returns.

    Aligns with ``specs/020-shared-research-execution/net-metrics-reporting.md``
    (``*_return_pct_gross`` / ``*_return_pct_net``, ``cost_round_trip_bps``).
    Cumulative P&L vs starting capital uses ``cumulative_return_pct_*`` = ``(equity - 1) * 100``.
    """
    cum_gross = [(e - 1.0) * 100.0 for e in res.equity_gross]
    cum_net = [(e - 1.0) * 100.0 for e in res.equity_net]
    period_gross_pct = [r * 100.0 for r in res.period_returns_gross]
    period_net_pct = [r * 100.0 for r in res.period_returns_net]
    return {
        "cost_round_trip_bps": res.cost_round_trip_bps,
        "cost_model": res.cost_model,
        "trade_count": len(res.trades),
        "skip_count": len(res.skips),
        "skips": [{"reason": s.reason, "signal_date": s.signal_date, "detail": s.detail} for s in res.skips],
        "trades": [
            {
                "entry_date": t.entry_date.isoformat(),
                "exit_date": t.exit_date.isoformat(),
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "trade_return_pct_gross": t.trade_return_pct_gross,
                "trade_return_pct_net": t.trade_return_pct_net,
            }
            for t in res.trades
        ],
        "period_trade_return_pct_gross": period_gross_pct,
        "period_trade_return_pct_net": period_net_pct,
        "cumulative_return_pct_gross": cum_gross,
        "cumulative_return_pct_net": cum_net,
        "final_cumulative_return_pct_gross": cum_gross[-1] if cum_gross else 0.0,
        "final_cumulative_return_pct_net": cum_net[-1] if cum_net else 0.0,
        "max_drawdown_pct_gross": res.max_drawdown_pct_gross,
        "max_drawdown_pct_net": res.max_drawdown_pct_net,
    }
