"""S7: deterministic daily feature matrix + gated rule search (spec 025).

Hold-out: search uses only rows with date <= train_end; reporting splits trades by entry_date.
Explicit overfitting risk: CLI requires acknowledgement before search runs.

This module is intentionally conservative: small discrete search space, no adaptive re-tuning
on the test window, complexity penalty on multi-condition rules.
"""

from __future__ import annotations

import csv
import json
import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal

from backend.app.config import get_settings
from backend.app.services.daily_frequency_strategy_research import DailyBar as FreqDailyBar
from backend.app.services.research_execution.daily_simple_backtest import (
    DailyBar as SimDailyBar,
    DailySimpleBacktestConfig,
    run_daily_simple_long_only_backtest,
)
from backend.app.services.research_execution.run_envelope import ResearchRunEnvelope

logger = logging.getLogger(__name__)

S7_FEATURE_MATRIX_VERSION = "s7_v1"

FeatureName = Literal["ret_1", "ret_5", "gap_pct", "range_pct", "vol_z"]
RuleOp = Literal["gt", "lt"]

FEATURE_COLUMNS: tuple[str, ...] = ("date", "ret_1", "ret_5", "gap_pct", "range_pct", "vol_z")
ALLOWED_FEATURES: frozenset[str] = frozenset({"ret_1", "ret_5", "gap_pct", "range_pct", "vol_z"})


@dataclass(frozen=True)
class RuleCondition:
    feature: FeatureName
    op: RuleOp
    threshold: float


@dataclass(frozen=True)
class RuleSpec:
    """Conjunctive rule: all conditions must hold on the signal day."""

    conditions: tuple[RuleCondition, ...]

    def complexity(self) -> int:
        return len(self.conditions)


@dataclass(frozen=True)
class S7FeatureRow:
    d: date
    ret_1: float
    ret_5: float
    gap_pct: float
    range_pct: float
    vol_z: float


def _to_sim_bars(bars: list[FreqDailyBar]) -> list[SimDailyBar]:
    return [SimDailyBar(d=b.d, open=b.open, high=b.high, low=b.low, close=b.close) for b in bars]


def _rolling_mean_std(window: list[float]) -> tuple[float, float]:
    if not window:
        return float("nan"), float("nan")
    mu = sum(window) / len(window)
    if len(window) < 2:
        return mu, float("nan")
    var = sum((x - mu) ** 2 for x in window) / (len(window) - 1)
    sig = math.sqrt(var) if var > 0 else 0.0
    return mu, sig


def build_feature_rows_from_bars(bars: list[FreqDailyBar], *, vol_z_window: int) -> list[S7FeatureRow]:
    """Build per-day feature rows from sorted OHLCV bars; drops warm-up days with incomplete history."""
    if vol_z_window < 2:
        raise ValueError("vol_z_window must be >= 2")
    w = max(5, vol_z_window)
    out: list[S7FeatureRow] = []
    n = len(bars)
    for i in range(n):
        b = bars[i]
        if i < w or i < 5:
            continue
        prev = bars[i - 1]
        if prev.close <= 0 or b.close <= 0:
            continue
        ret_1 = b.close / prev.close - 1.0
        gap_pct = (b.open - prev.close) / prev.close if prev.close else float("nan")
        range_pct = (b.high - b.low) / b.close if b.close else float("nan")
        lag5 = bars[i - 5]
        ret_5 = b.close / lag5.close - 1.0 if lag5.close > 0 else float("nan")
        vol_hist = [float(bars[j].volume) for j in range(i - w, i)]
        v_today = float(b.volume)
        mu, sig = _rolling_mean_std(vol_hist)
        vol_z = (v_today - mu) / sig if sig and sig > 0 else 0.0

        if any(math.isnan(x) or math.isinf(x) for x in (ret_1, ret_5, gap_pct, range_pct, vol_z)):
            continue
        out.append(
            S7FeatureRow(
                d=b.d,
                ret_1=ret_1,
                ret_5=ret_5,
                gap_pct=gap_pct,
                range_pct=range_pct,
                vol_z=vol_z,
            )
        )
    return out


def write_feature_matrix_csv(
    path: Path | str,
    rows: list[S7FeatureRow],
    *,
    symbol: str,
    meta_extra: dict[str, Any] | None = None,
) -> Path:
    """Write CSV + sidecar ``*.meta.json`` (version, symbol, lineage)."""
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(FEATURE_COLUMNS))
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    "date": r.d.isoformat(),
                    "ret_1": f"{r.ret_1:.10g}",
                    "ret_5": f"{r.ret_5:.10g}",
                    "gap_pct": f"{r.gap_pct:.10g}",
                    "range_pct": f"{r.range_pct:.10g}",
                    "vol_z": f"{r.vol_z:.10g}",
                }
            )
    settings = get_settings()
    meta = {
        "feature_matrix_version": S7_FEATURE_MATRIX_VERSION,
        "symbol": symbol.strip().upper(),
        "n_rows": len(rows),
        "vol_z_window": settings.s7_vol_z_window,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    if meta_extra:
        meta.update(meta_extra)
    meta_path = p.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    logger.info("Wrote S7 feature matrix %s (%s rows) and %s", p, len(rows), meta_path)
    return p


def read_feature_matrix_csv(path: Path | str) -> tuple[list[S7FeatureRow], dict[str, Any]]:
    p = Path(path).resolve()
    if not p.is_file():
        raise FileNotFoundError(str(p))
    meta_path = p.with_suffix(".meta.json")
    meta: dict[str, Any] = {}
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning("S7 meta JSON unreadable %s: %s", meta_path, exc)

    rows: list[S7FeatureRow] = []
    with p.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header")
        expected = set(FEATURE_COLUMNS)
        if not expected.issubset(set(reader.fieldnames)):
            raise ValueError(f"CSV must contain columns {sorted(expected)}; got {reader.fieldnames}")
        for row in reader:
            rows.append(
                S7FeatureRow(
                    d=date.fromisoformat(str(row["date"]).strip()[:10]),
                    ret_1=float(row["ret_1"]),
                    ret_5=float(row["ret_5"]),
                    gap_pct=float(row["gap_pct"]),
                    range_pct=float(row["range_pct"]),
                    vol_z=float(row["vol_z"]),
                )
            )
    rows.sort(key=lambda r: r.d)
    return rows, meta


def _quantile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return float("nan")
    if q <= 0:
        return sorted_vals[0]
    if q >= 1:
        return sorted_vals[-1]
    pos = q * (len(sorted_vals) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_vals[lo]
    w = pos - lo
    return sorted_vals[lo] * (1 - w) + sorted_vals[hi] * w


def _train_values(rows: Iterable[S7FeatureRow], feature: FeatureName) -> list[float]:
    return sorted(getattr(r, feature) for r in rows)


def rule_matches_row(row: S7FeatureRow, rule: RuleSpec) -> bool:
    for c in rule.conditions:
        if c.feature not in ALLOWED_FEATURES:
            return False
        v = getattr(row, c.feature)
        if c.op == "gt" and not (v > c.threshold):
            return False
        if c.op == "lt" and not (v < c.threshold):
            return False
    return True


def _signals_for_rule(
    feature_by_date: dict[date, S7FeatureRow], all_dates: list[date], rule: RuleSpec
) -> dict[date, int]:
    sig: dict[date, int] = {}
    for d in all_dates:
        row = feature_by_date.get(d)
        if row is None:
            continue
        sig[d] = 1 if rule_matches_row(row, rule) else 0
    return sig


def _merge_signals(all_dates: list[date], explicit: dict[date, int]) -> dict[date, int]:
    return {d: int(explicit.get(d, 0)) for d in all_dates}


def enumerate_candidate_rules(
    train_rows: list[S7FeatureRow],
    *,
    feature_names: list[FeatureName],
    quantile_levels: list[float],
    max_conditions: int,
    max_rules: int,
) -> list[RuleSpec]:
    """Discrete search space from train quantiles only (no test peeking)."""
    if max_conditions < 1 or max_conditions > 3:
        raise ValueError("max_conditions must be in 1..3")
    if not train_rows:
        return []

    by_feat: dict[FeatureName, list[float]] = {f: _train_values(train_rows, f) for f in feature_names}
    thr_by_feat: dict[FeatureName, list[float]] = {}
    for f in feature_names:
        vals = by_feat[f]
        thr_by_feat[f] = [_quantile(vals, q) for q in quantile_levels]

    rules: list[RuleSpec] = []

    def push_rule(r: RuleSpec) -> None:
        if len(rules) >= max_rules:
            return
        rules.append(r)

    # 1-condition rules
    for f in feature_names:
        for thr in thr_by_feat[f]:
            if math.isnan(thr):
                continue
            for op in ("gt", "lt"):
                push_rule(RuleSpec(conditions=(RuleCondition(feature=f, op=op, threshold=thr),)))  # type: ignore[arg-type]
                if len(rules) >= max_rules:
                    return rules

    if max_conditions < 2:
        return rules

    # 2-condition rules: distinct features, limited Cartesian product
    for i, f1 in enumerate(feature_names):
        for f2 in feature_names[i + 1 :]:
            for thr1 in thr_by_feat[f1]:
                for thr2 in thr_by_feat[f2]:
                    if math.isnan(thr1) or math.isnan(thr2):
                        continue
                    for op1 in ("gt", "lt"):
                        for op2 in ("gt", "lt"):
                            c1 = RuleCondition(feature=f1, op=op1, threshold=thr1)  # type: ignore[arg-type]
                            c2 = RuleCondition(feature=f2, op=op2, threshold=thr2)  # type: ignore[arg-type]
                            push_rule(RuleSpec(conditions=(c1, c2)))
                            if len(rules) >= max_rules:
                                return rules
    return rules


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def _rule_to_dict(rule: RuleSpec) -> dict[str, Any]:
    return {
        "conditions": [{"feature": c.feature, "op": c.op, "threshold": c.threshold} for c in rule.conditions],
        "complexity": rule.complexity(),
    }


def run_rule_search(
    *,
    bars: list[FreqDailyBar],
    feature_rows: list[S7FeatureRow],
    train_end: date,
    ack_overfitting_risk: bool,
    symbol: str,
) -> dict[str, Any]:
    """Score discrete rules on train (date <= train_end); report test trade subset (entry > train_end)."""
    if not ack_overfitting_risk:
        raise ValueError("refusing S7 search without explicit ack_overfitting_risk=True")

    settings = get_settings()
    if not feature_rows:
        return {
            "kind": "s7_rule_discovery_result",
            "error": "no_feature_rows",
            "message": "No feature rows; need more price history or check vol_z window.",
        }

    if train_end < feature_rows[0].d:
        return {
            "kind": "s7_rule_discovery_result",
            "error": "invalid_train_end",
            "message": "train_end must be on or after the first feature row date.",
            "first_date": str(feature_rows[0].d),
        }

    test_feat = [r for r in feature_rows if r.d > train_end]
    min_h = max(1, settings.s7_min_hold_out_feature_rows)
    if len(test_feat) < min_h:
        return {
            "kind": "s7_rule_discovery_result",
            "error": "insufficient_hold_out",
            "message": f"Need at least {min_h} feature rows strictly after train_end "
            f"for frozen hold-out reporting (got {len(test_feat)}).",
            "last_date": str(feature_rows[-1].d),
        }

    train_rows = [r for r in feature_rows if r.d <= train_end]
    if len(train_rows) < max(20, settings.s7_vol_z_window):
        return {
            "kind": "s7_rule_discovery_result",
            "error": "insufficient_train_rows",
            "n_train": len(train_rows),
        }

    features_cfg = [x.strip() for x in settings.s7_search_feature_names.split(",") if x.strip()]
    feature_names: list[FeatureName] = []
    for x in features_cfg:
        if x in ("ret_1", "ret_5", "gap_pct", "range_pct", "vol_z"):
            feature_names.append(x)  # type: ignore[arg-type]
        else:
            logger.warning("Ignoring unknown S7 feature name %r", x)
    if not feature_names:
        return {"kind": "s7_rule_discovery_result", "error": "no_valid_feature_names"}

    q_levels = []
    for part in settings.s7_search_quantiles.split(","):
        part = part.strip()
        if not part:
            continue
        q_levels.append(float(part))
    if not q_levels:
        q_levels = [0.33, 0.67]

    sim_bars = _to_sim_bars(bars)
    all_feature_dates = sorted({r.d for r in feature_rows})
    feature_by_date = {r.d: r for r in feature_rows}
    all_bar_dates = [b.d for b in sim_bars]

    candidates = enumerate_candidate_rules(
        train_rows,
        feature_names=feature_names,
        quantile_levels=q_levels,
        max_conditions=max(1, min(3, settings.s7_max_rule_conditions)),
        max_rules=max(10, settings.s7_max_candidate_rules),
    )

    complexity_penalty = float(settings.s7_complexity_penalty)
    horizon = max(1, settings.s7_forward_horizon_days)
    cost_bps = float(settings.research_default_round_trip_cost_bps)

    cfg = DailySimpleBacktestConfig(
        entry="same_close",
        horizon_days=horizon,
        round_trip_cost_bps=cost_bps,
    )

    scored: list[tuple[float, RuleSpec, dict[str, Any]]] = []

    for rule in candidates:
        raw_sig = _signals_for_rule(feature_by_date, all_feature_dates, rule)
        signals = _merge_signals(all_bar_dates, raw_sig)
        result = run_daily_simple_long_only_backtest(sim_bars, signals, cfg)
        train_returns = [t.trade_return_pct_net for t in result.trades if t.entry_date <= train_end]
        test_returns = [t.trade_return_pct_net for t in result.trades if t.entry_date > train_end]
        train_mean = _mean(train_returns)
        if math.isnan(train_mean):
            train_mean = 0.0
        adjusted = train_mean - complexity_penalty * max(0, rule.complexity() - 1)
        detail = {
            "rule": _rule_to_dict(rule),
            "train": {
                "n_trades": len(train_returns),
                "mean_trade_return_pct_net": train_mean,
                "adjusted_score": adjusted,
            },
            "test": {
                "n_trades": len(test_returns),
                "mean_trade_return_pct_net": _mean(test_returns),
            },
            "all_period_max_drawdown_pct_net": result.max_drawdown_pct_net,
        }
        scored.append((adjusted, rule, detail))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_k = max(1, min(20, settings.s7_top_rules_reported))
    top = [d for _, _, d in scored[:top_k]]

    sym_u = symbol.strip().upper()
    env = ResearchRunEnvelope.from_context(
        run_kind="s7_rule_discovery",
        strategy_family="S7_rule_discovery",
        eval_start=feature_rows[0].d,
        eval_end=feature_rows[-1].d,
        universe_label=f"single_symbol:{sym_u}",
        symbols=[sym_u],
        cost_round_trip_bps=cost_bps,
        notes="S7 search: train/test split by trade entry_date vs train_end; high false-discovery risk.",
    )

    return {
        "kind": "s7_rule_discovery_result",
        "eval_window": {"start": str(feature_rows[0].d), "end": str(feature_rows[-1].d)},
        "symbols_requested": [sym_u],
        "feature_matrix_version": S7_FEATURE_MATRIX_VERSION,
        "protocol": {
            "train_end": str(train_end),
            "hold_out_note": "Test metrics use trades with entry_date > train_end only; "
            "no parameter refit on test window.",
            "entry_mode": cfg.entry,
            "forward_horizon_days": horizon,
            "complexity_penalty": complexity_penalty,
            "n_candidates": len(candidates),
            "n_train_rows": len(train_rows),
        },
        "envelope": env.to_json_dict(),
        "top_rules": top,
        "warnings": [
            "Multiple testing and selection bias: top_rules are chosen on train scores; "
            "test metrics are not adjusted for search breadth.",
        ],
    }
