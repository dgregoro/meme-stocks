"""Leader-follower paper trading simulation from signals + price bars."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timezone
from itertools import groupby
from typing import Any, Literal, cast

from sqlalchemy.orm import Session

from backend.app.data.repositories.leader_follower_paper_run_repo import LeaderFollowerPaperRunRepository
from backend.app.data.repositories.leader_follower_paper_trade_repo import LeaderFollowerPaperTradeRepository
from backend.app.data.repositories.leader_follower_signal_repo import LeaderFollowerSignalRepository
from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.models.leader_follower_paper_run import LeaderFollowerPaperRun
from backend.app.models.leader_follower_paper_trade import LeaderFollowerPaperTrade
from backend.app.models.leader_follower_signal import LeaderFollowerSignal
from backend.app.services.regime_filter_service import RegimeFilterParams, evaluate_regime_filter
from backend.app.services.sector_confirmation_service import (
    SectorConfirmationParams,
    SectorTrendMethod,
    evaluate_sector_confirmation,
)

EntryMode = Literal["next_open", "same_close"]
ExitMode = Literal["fixed_days", "early_exit"]


@dataclass(frozen=True)
class PaperTradingConfig:
    """Execution rules for one simulation run."""

    entry_mode: EntryMode = "next_open"
    exit_mode: ExitMode = "fixed_days"
    holding_days: int = 3
    max_positions_per_event: int = 2
    min_pair_score: float | None = None
    per_trade_cost_pct: float = 0.1
    sector_confirmation_enabled: bool = False
    sector_trend_method: SectorTrendMethod = "ma_above"
    sector_trend_window: int = 10
    minimum_sector_return_pct: float = 0.0
    require_positive_trend: bool = True
    sector_etf_symbol: str | None = None
    regime_filter_enabled: bool = False
    regime_benchmark_symbol: str = "SPY"
    market_trend_window: int = 20
    require_market_uptrend: bool = True
    volatility_window: int = 10
    volatility_threshold: float = 0.02
    require_low_volatility: bool = False
    regime_sector_strength_required: bool = False

    def to_json_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    def sector_confirmation_params(self) -> SectorConfirmationParams:
        return SectorConfirmationParams(
            enabled=self.sector_confirmation_enabled,
            sector_etf_symbol=self.sector_etf_symbol,
            sector_trend_method=self.sector_trend_method,
            sector_trend_window=self.sector_trend_window,
            minimum_sector_return_pct=self.minimum_sector_return_pct,
            require_positive_trend=self.require_positive_trend,
        )

    def regime_filter_params(self) -> RegimeFilterParams:
        return RegimeFilterParams(
            enabled=self.regime_filter_enabled,
            regime_benchmark_symbol=self.regime_benchmark_symbol,
            market_trend_window=self.market_trend_window,
            require_market_uptrend=self.require_market_uptrend,
            volatility_window=self.volatility_window,
            volatility_threshold=self.volatility_threshold,
            require_low_volatility=self.require_low_volatility,
            regime_sector_strength_required=self.regime_sector_strength_required,
        )

    @staticmethod
    def from_json_dict(d: dict[str, Any]) -> PaperTradingConfig:
        raw_method = d.get("sector_trend_method", "ma_above")
        if raw_method not in ("ma_above", "rolling_return", "combined"):
            raise ValueError(f"Invalid sector_trend_method: {raw_method!r}")
        etf_override = d.get("sector_etf_symbol")
        if etf_override is not None and not isinstance(etf_override, str):
            raise ValueError("sector_etf_symbol must be a string or null")
        regime_sector = bool(d.get("regime_sector_strength_required", False))
        sector_on = bool(d.get("sector_confirmation_enabled", False))
        if regime_sector and not sector_on:
            raise ValueError("regime_sector_strength_requires_sector_confirmation_enabled")
        bench = d.get("regime_benchmark_symbol", "SPY")
        if not isinstance(bench, str) or not bench.strip():
            raise ValueError("regime_benchmark_symbol must be a non-empty string")
        req_up = bool(d.get("require_market_uptrend", True))
        mtw = int(d.get("market_trend_window", 20))
        if req_up and mtw < 1:
            raise ValueError("market_trend_window must be >= 1 when require_market_uptrend")
        req_lv = bool(d.get("require_low_volatility", False))
        vw = int(d.get("volatility_window", 10))
        if req_lv and vw < 2:
            raise ValueError("volatility_window must be >= 2 when require_low_volatility")
        return PaperTradingConfig(
            entry_mode=d.get("entry_mode", "next_open"),
            exit_mode=d.get("exit_mode", "fixed_days"),
            holding_days=int(d.get("holding_days", 3)),
            max_positions_per_event=int(d.get("max_positions_per_event", 2)),
            min_pair_score=d.get("min_pair_score"),
            per_trade_cost_pct=float(d.get("per_trade_cost_pct", 0.1)),
            sector_confirmation_enabled=bool(d.get("sector_confirmation_enabled", False)),
            sector_trend_method=cast(SectorTrendMethod, raw_method),
            sector_trend_window=int(d.get("sector_trend_window", 10)),
            minimum_sector_return_pct=float(d.get("minimum_sector_return_pct", 0.0)),
            require_positive_trend=bool(d.get("require_positive_trend", True)),
            sector_etf_symbol=etf_override,
            regime_filter_enabled=bool(d.get("regime_filter_enabled", False)),
            regime_benchmark_symbol=bench.strip().upper(),
            market_trend_window=mtw,
            require_market_uptrend=req_up,
            volatility_window=vw,
            volatility_threshold=float(d.get("volatility_threshold", 0.02)),
            require_low_volatility=req_lv,
            regime_sector_strength_required=regime_sector,
        )


def apply_round_trip_cost(gross_return_pct: float, per_trade_cost_pct: float) -> float:
    """Subtract one round-trip cost (percentage points) from gross return."""
    return gross_return_pct - per_trade_cost_pct


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


def _utc_noon(d: date) -> datetime:
    return datetime.combine(d, time(12, 0), tzinfo=timezone.utc)


def _first_trading_day_after(dates: list[date], signal_date: date) -> int | None:
    """Index of first date strictly after signal_date, or None."""
    for i, d in enumerate(dates):
        if d > signal_date:
            return i
    return None


def _index_of(dates: list[date], d: date) -> int | None:
    try:
        return dates.index(d)
    except ValueError:
        return None


def _resolve_entry_date(
    signal: LeaderFollowerSignal,
    dates: list[date],
    cfg: PaperTradingConfig,
) -> date | None:
    """First calendar day of follower entry (same as ``_resolve_trade`` entry side)."""
    if not dates:
        return None
    if cfg.entry_mode == "same_close":
        ei = _index_of(dates, signal.signal_date)
        return dates[ei] if ei is not None else None
    ei = _first_trading_day_after(dates, signal.signal_date)
    return dates[ei] if ei is not None else None


def _select_signals_per_event(
    signals: list[LeaderFollowerSignal],
    max_positions: int,
) -> list[LeaderFollowerSignal]:
    """Group by (leader, signal_date), rank, take top N per group. Deterministic."""
    signals_sorted = sorted(signals, key=lambda s: (s.signal_date, s.leader_symbol, s.follower_symbol))
    out: list[LeaderFollowerSignal] = []
    for _key, group in groupby(
        signals_sorted,
        key=lambda s: (s.leader_symbol, s.signal_date),
    ):
        ranked = sorted(
            list(group),
            key=lambda s: (-s.strength_score, -s.leader_return_pct, s.follower_symbol),
        )
        out.extend(ranked[:max_positions])
    return out


def _resolve_trade(
    signal: LeaderFollowerSignal,
    dates: list[date],
    price_repo: PriceDataRepository,
    cfg: PaperTradingConfig,
) -> dict[str, Any] | None:
    """Return trade fields dict or None if skipped."""
    follower = signal.follower_symbol
    if not dates:
        return None

    if cfg.entry_mode == "same_close":
        ei = _index_of(dates, signal.signal_date)
        if ei is None:
            return None
        entry_date = dates[ei]
        bar_e = price_repo.get_for_date(follower, entry_date)
        if bar_e is None or bar_e.close <= 0:
            return None
        entry_price = float(bar_e.close)
    else:
        ei = _first_trading_day_after(dates, signal.signal_date)
        if ei is None:
            return None
        entry_date = dates[ei]
        bar_e = price_repo.get_for_date(follower, entry_date)
        if bar_e is None or bar_e.open <= 0:
            return None
        entry_price = float(bar_e.open)

    entry_idx = _index_of(dates, entry_date)
    if entry_idx is None:
        return None

    fixed_exit_idx = entry_idx + cfg.holding_days
    if fixed_exit_idx >= len(dates):
        return None

    exit_idx = fixed_exit_idx
    if cfg.exit_mode == "early_exit":
        for j in range(entry_idx + 1, fixed_exit_idx + 1):
            bar_j = price_repo.get_for_date(follower, dates[j])
            if bar_j is None:
                continue
            if float(bar_j.close) < entry_price:
                exit_idx = j
                break

    exit_date = dates[exit_idx]
    bar_x = price_repo.get_for_date(follower, exit_date)
    if bar_x is None or bar_x.close <= 0:
        return None
    exit_price = float(bar_x.close)

    gross = (exit_price / entry_price - 1.0) * 100.0
    net = apply_round_trip_cost(gross, cfg.per_trade_cost_pct)
    holding_td = exit_idx - entry_idx

    return {
        "entry_date": entry_date,
        "exit_date": exit_date,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "gross_return_pct": gross,
        "net_return_pct": net,
        "holding_period_days": holding_td,
        "entry_time": _utc_noon(entry_date),
        "exit_time": _utc_noon(exit_date),
    }


@dataclass(frozen=True)
class PaperSimulationMetrics:
    """Aggregate metrics from one simulation window (no persistence)."""

    total_trades: int
    skipped_count: int
    skipped_sector_confirmation_count: int
    skipped_regime_filter_count: int
    win_rate: float
    avg_return_pct: float
    cumulative_return_pct: float
    max_drawdown_pct: float

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "total_trades": self.total_trades,
            "skipped_count": self.skipped_count,
            "skipped_sector_confirmation_count": self.skipped_sector_confirmation_count,
            "skipped_regime_filter_count": self.skipped_regime_filter_count,
            "cumulative_return_pct": self.cumulative_return_pct,
            "avg_return_pct": self.avg_return_pct,
            "win_rate": self.win_rate,
            "max_drawdown_pct": self.max_drawdown_pct,
        }


def run_paper_trading_core(
    db: Session,
    start_date: date,
    end_date: date,
    cfg: PaperTradingConfig,
) -> tuple[PaperSimulationMetrics, list[dict[str, Any]]]:
    """Load signals and prices, resolve trades, return metrics + trade payloads (with ``signal`` key)."""
    sig_repo = LeaderFollowerSignalRepository(db)
    price_repo = PriceDataRepository(db)

    raw = sig_repo.list_signals(
        limit=None,
        since_date=start_date,
        until_date=end_date,
    )
    signals = list(raw)

    if cfg.min_pair_score is not None:
        signals = [s for s in signals if s.strength_score >= cfg.min_pair_score]

    signals.sort(key=lambda s: (s.signal_date, s.leader_symbol, s.follower_symbol))
    selected = _select_signals_per_event(signals, cfg.max_positions_per_event)

    skipped = 0
    skipped_sector = 0
    skipped_regime = 0
    trades_payload: list[dict[str, Any]] = []

    cal_cache: dict[str, list[date]] = {}
    sect_params = cfg.sector_confirmation_params()
    regime_params = cfg.regime_filter_params()

    for sig in sorted(selected, key=lambda s: (s.signal_date, s.leader_symbol, s.follower_symbol)):
        follower = sig.follower_symbol
        if follower not in cal_cache:
            cal_cache[follower] = price_repo.list_dates_for_symbol(follower)
        dates = cal_cache[follower]
        entry_date = _resolve_entry_date(sig, dates, cfg)
        if entry_date is None:
            skipped += 1
            continue
        allow, sector_snap = evaluate_sector_confirmation(
            price_repo,
            sig.leader_symbol,
            entry_date,
            sect_params,
        )
        if not allow:
            skipped += 1
            skipped_sector += 1
            continue

        sect_pass = sector_snap.get("sector_confirmation_passed") if sector_snap else None
        regime_allow, regime_snap = evaluate_regime_filter(
            price_repo,
            entry_date,
            regime_params,
            sector_confirmation_passed=bool(sect_pass) if sect_pass is not None else None,
        )
        if not regime_allow:
            skipped += 1
            skipped_regime += 1
            continue

        row = _resolve_trade(sig, dates, price_repo, cfg)
        if row is None:
            skipped += 1
            continue
        row["signal"] = sig
        if sector_snap:
            row["sector_etf_symbol"] = sector_snap.get("sector_etf_symbol")
            row["sector_close"] = sector_snap.get("sector_close")
            row["sector_ma"] = sector_snap.get("sector_ma")
            row["sector_rolling_return_pct"] = sector_snap.get("sector_rolling_return_pct")
            row["sector_confirmation_passed"] = sector_snap.get("sector_confirmation_passed")
        if regime_snap:
            row["regime_benchmark_symbol"] = regime_snap.get("regime_benchmark_symbol")
            row["regime_decision_date"] = regime_snap.get("regime_decision_date")
            row["regime_benchmark_close"] = regime_snap.get("regime_benchmark_close")
            row["regime_benchmark_ma"] = regime_snap.get("regime_benchmark_ma")
            row["regime_market_uptrend_passed"] = regime_snap.get("regime_market_uptrend_passed")
            row["regime_volatility"] = regime_snap.get("regime_volatility")
            row["regime_low_volatility_passed"] = regime_snap.get("regime_low_volatility_passed")
            row["regime_sector_strength_passed"] = regime_snap.get("regime_sector_strength_passed")
            row["regime_filter_passed"] = regime_snap.get("regime_filter_passed")
        trades_payload.append(row)

    equities: list[float] = [1.0]
    for t in trades_payload:
        eq = equities[-1] * (1.0 + t["net_return_pct"] / 100.0)
        equities.append(eq)

    n = len(trades_payload)
    wins = sum(1 for t in trades_payload if t["net_return_pct"] > 0)
    win_rate = (wins / n) if n else 0.0
    avg_ret = sum(t["net_return_pct"] for t in trades_payload) / n if n else 0.0
    cum_pct = (equities[-1] - 1.0) * 100.0 if equities else 0.0
    max_dd = max_drawdown_from_equity(equities)

    metrics = PaperSimulationMetrics(
        total_trades=n,
        skipped_count=skipped,
        skipped_sector_confirmation_count=skipped_sector,
        skipped_regime_filter_count=skipped_regime,
        win_rate=win_rate,
        avg_return_pct=avg_ret,
        cumulative_return_pct=cum_pct,
        max_drawdown_pct=max_dd,
    )
    return metrics, trades_payload


def compute_paper_trading_metrics(
    db: Session,
    start_date: date,
    end_date: date,
    cfg: PaperTradingConfig,
) -> PaperSimulationMetrics:
    """Run simulation for one window without persisting runs or trades."""
    metrics, _ = run_paper_trading_core(db, start_date, end_date, cfg)
    return metrics


def run_paper_trading_simulation(
    db: Session,
    start_date: date,
    end_date: date,
    cfg: PaperTradingConfig,
) -> LeaderFollowerPaperRun:
    """Execute simulation, persist run + trades, return the run row (with trades loaded optional)."""
    run_repo = LeaderFollowerPaperRunRepository(db)
    trade_repo = LeaderFollowerPaperTradeRepository(db)

    metrics, trades_payload = run_paper_trading_core(db, start_date, end_date, cfg)

    run = LeaderFollowerPaperRun(
        config_json=json.dumps(cfg.to_json_dict()),
        start_date=start_date,
        end_date=end_date,
        total_trades=metrics.total_trades,
        skipped_count=metrics.skipped_count,
        skipped_sector_confirmation_count=metrics.skipped_sector_confirmation_count,
        skipped_regime_filter_count=metrics.skipped_regime_filter_count,
        win_rate=metrics.win_rate,
        avg_return_pct=metrics.avg_return_pct,
        cumulative_return_pct=metrics.cumulative_return_pct,
        max_drawdown_pct=metrics.max_drawdown_pct,
    )
    run_repo.add(run)
    db.flush()

    for t in trades_payload:
        sig = t["signal"]
        tr = LeaderFollowerPaperTrade(
            run_id=run.id,
            leader_symbol=sig.leader_symbol,
            follower_symbol=sig.follower_symbol,
            signal_date=sig.signal_date,
            signal_id=sig.id,
            entry_price=t["entry_price"],
            exit_price=t["exit_price"],
            entry_time=t["entry_time"],
            exit_time=t["exit_time"],
            holding_period_days=t["holding_period_days"],
            gross_return_pct=t["gross_return_pct"],
            net_return_pct=t["net_return_pct"],
            sector_etf_symbol=t.get("sector_etf_symbol"),
            sector_close=t.get("sector_close"),
            sector_ma=t.get("sector_ma"),
            sector_rolling_return_pct=t.get("sector_rolling_return_pct"),
            sector_confirmation_passed=t.get("sector_confirmation_passed"),
            regime_benchmark_symbol=t.get("regime_benchmark_symbol"),
            regime_decision_date=t.get("regime_decision_date"),
            regime_benchmark_close=t.get("regime_benchmark_close"),
            regime_benchmark_ma=t.get("regime_benchmark_ma"),
            regime_market_uptrend_passed=t.get("regime_market_uptrend_passed"),
            regime_volatility=t.get("regime_volatility"),
            regime_low_volatility_passed=t.get("regime_low_volatility_passed"),
            regime_sector_strength_passed=t.get("regime_sector_strength_passed"),
            regime_filter_passed=t.get("regime_filter_passed"),
        )
        trade_repo.add(tr)

    db.commit()
    db.refresh(run)
    return run
