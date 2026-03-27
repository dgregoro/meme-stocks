"""Rolling walk-forward robustness evaluation (many splits × modest candidate set)."""

from __future__ import annotations

import hashlib
import json
import logging
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from backend.app.config import Settings, get_settings
from backend.app.data.repositories.leader_follower_robustness_aggregate_repo import (
    LeaderFollowerRobustnessAggregateRepository,
)
from backend.app.data.repositories.leader_follower_robustness_run_repo import (
    LeaderFollowerRobustnessRunRepository,
)
from backend.app.data.repositories.leader_follower_robustness_split_result_repo import (
    LeaderFollowerRobustnessSplitResultRepository,
)
from backend.app.models.leader_follower_robustness_aggregate import LeaderFollowerRobustnessAggregate
from backend.app.models.leader_follower_robustness_run import LeaderFollowerRobustnessRun
from backend.app.models.leader_follower_robustness_split_result import LeaderFollowerRobustnessSplitResult
from backend.app.services.leader_follower_paper_trading_service import (
    PaperSimulationMetrics,
    PaperTradingConfig,
    compute_paper_trading_metrics,
)
from backend.app.services.leader_follower_walk_forward_service import (
    ALLOWED_GRID_KEYS,
    expand_grid_points,
)
from backend.app.services.rolling_split_utils import RollingSplitValidationError, generate_monthly_rolling_splits

logger = logging.getLogger(__name__)

RANKING_ROLLING_ROBUSTNESS_V1 = "rolling_robustness_v1"

DEFAULT_ROLLING_RANKING: dict[str, Any] = {
    "method": RANKING_ROLLING_ROBUSTNESS_V1,
    "min_trades_validate": 5,
    "w_dd": 0.25,
    "w_gap": 0.5,
    "w_frac": 10.0,
    "penalty_ineligible": 25.0,
}


class RollingRobustnessValidationError(ValueError):
    """Invalid grid/candidates, ranking method, or work cap."""


def read_rolling_robustness_file(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as exc:
        raise RollingRobustnessValidationError(f"Invalid JSON in robustness file: {exc}") from exc
    if not isinstance(raw, dict):
        raise RollingRobustnessValidationError("File must contain a JSON object")
    return raw


def _merge_rolling_ranking_defaults(ranking: dict[str, Any]) -> dict[str, Any]:
    out = dict(DEFAULT_ROLLING_RANKING)
    out.update(ranking)
    return out


def _load_grid_branch(raw: dict[str, Any], ranking: dict[str, Any], max_combo: int) -> list[dict[str, Any]]:
    base = dict(raw.get("base_config") or {})
    grid = raw.get("grid")
    if not isinstance(grid, dict) or not grid:
        raise RollingRobustnessValidationError("grid must be a non-empty object")
    unknown = set(grid.keys()) - ALLOWED_GRID_KEYS
    if unknown:
        raise RollingRobustnessValidationError(f"Unsupported grid keys: {sorted(unknown)}")
    for key, values in grid.items():
        if not isinstance(values, list) or len(values) == 0:
            raise RollingRobustnessValidationError(f"grid.{key} must be a non-empty list")
    wrapped = {"base_config": base, "grid": grid, "ranking": ranking}
    points = expand_grid_points(wrapped, max_combo)
    return [{**base, **pt} for pt in points]


def _load_candidates_branch(raw: dict[str, Any], max_n: int) -> list[dict[str, Any]]:
    base = dict(raw.get("base_config") or {})
    cands = raw.get("candidates")
    if not isinstance(cands, list) or not cands:
        raise RollingRobustnessValidationError("candidates must be a non-empty list")
    if len(cands) > max_n:
        raise RollingRobustnessValidationError(f"candidates has {len(cands)} entries; max allowed is {max_n}")
    out: list[dict[str, Any]] = []
    for i, c in enumerate(cands):
        if not isinstance(c, dict):
            raise RollingRobustnessValidationError(f"candidates[{i}] must be an object")
        out.append({**base, **c})
    return out


def load_rolling_source_payload(
    raw: dict[str, Any],
    *,
    max_grid_points: int,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Return merged candidate dicts, ranking, and config snapshot (without rolling dates)."""
    ranking = _merge_rolling_ranking_defaults(dict(raw.get("ranking") or {}))
    if ranking.get("method") != RANKING_ROLLING_ROBUSTNESS_V1:
        raise RollingRobustnessValidationError(
            f"ranking.method must be {RANKING_ROLLING_ROBUSTNESS_V1!r} for robustness runs"
        )
    has_grid = isinstance(raw.get("grid"), dict) and bool(raw["grid"])
    c_raw = raw.get("candidates")
    has_cand = isinstance(c_raw, list) and len(c_raw) > 0
    if has_grid and has_cand:
        raise RollingRobustnessValidationError("Specify only one of grid or candidates")
    if not has_grid and not has_cand:
        raise RollingRobustnessValidationError("Provide a non-empty grid or candidates list")

    snapshot: dict[str, Any] = {
        "base_config": dict(raw.get("base_config") or {}),
        "ranking": ranking,
    }
    if has_grid:
        snapshot["grid"] = raw["grid"]
        snapshot["mode"] = "grid"
        points = _load_grid_branch(raw, ranking, max_grid_points)
    else:
        snapshot["candidates"] = raw["candidates"]
        snapshot["mode"] = "candidates"
        points = _load_candidates_branch(raw, max_grid_points)
    return points, ranking, snapshot


def _canonical_params(params: dict[str, Any]) -> str:
    return json.dumps(params, sort_keys=True)


def _params_hash(params: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_params(params).encode()).hexdigest()


def _score_and_aggregate_metrics(
    per_split: list[tuple[PaperSimulationMetrics, PaperSimulationMetrics, PaperSimulationMetrics | None]],
    ranking: dict[str, Any],
    *,
    has_test: bool,
) -> tuple[float, dict[str, Any]]:
    """``rolling_robustness_v1``: medians + consistency − penalties (not peak single-split)."""
    min_trades = int(ranking.get("min_trades_validate", 5))
    w_dd = float(ranking.get("w_dd", 0.25))
    w_gap = float(ranking.get("w_gap", 0.5))
    w_frac = float(ranking.get("w_frac", 10.0))
    penalty_ineligible = float(ranking.get("penalty_ineligible", 25.0))

    train_ret = [t.cumulative_return_pct for t, _, _ in per_split]
    val_ret = [v.cumulative_return_pct for _, v, _ in per_split]
    val_dd = [v.max_drawdown_pct for _, v, _ in per_split]
    val_trades = [v.total_trades for _, v, _ in per_split]
    gaps = [max(0.0, tr - vr) for tr, vr in zip(train_ret, val_ret)]

    n = len(val_ret)
    positive_validation_splits = sum(1 for v in val_ret if v > 0)
    frac_pos_val = positive_validation_splits / n if n else 0.0
    ineligible_splits = sum(1 for nt in val_trades if nt < min_trades)

    median_val = float(statistics.median(val_ret)) if val_ret else 0.0
    median_dd = float(statistics.median(val_dd)) if val_dd else 0.0
    median_gap = float(statistics.median(gaps)) if gaps else 0.0
    worst_val = float(min(val_ret)) if val_ret else 0.0

    positive_test_splits = 0
    median_test_ret: float | None = None
    frac_pos_test: float | None = None
    test_returns_nonempty: list[float] = []
    if has_test:
        for _, _, te in per_split:
            if te is None:
                continue
            test_returns_nonempty.append(te.cumulative_return_pct)
            if te.cumulative_return_pct > 0:
                positive_test_splits += 1
        nt = len(test_returns_nonempty)
        if nt:
            median_test_ret = float(statistics.median(test_returns_nonempty))
            frac_pos_test = sum(1 for x in test_returns_nonempty if x > 0) / nt

    score = (
        median_val
        + w_frac * (frac_pos_val - 0.5)
        - w_dd * median_dd
        - w_gap * median_gap
        - penalty_ineligible * float(ineligible_splits)
    )

    agg: dict[str, Any] = {
        "splits_evaluated": n,
        "positive_validation_splits": positive_validation_splits,
        "frac_positive_validation": frac_pos_val,
        "median_validation_cumulative_return_pct": median_val,
        "median_validation_max_drawdown_pct": median_dd,
        "median_train_to_validation_gap": median_gap,
        "worst_validation_cumulative_return_pct": worst_val,
        "ineligible_splits": ineligible_splits,
        "min_trades_validate": min_trades,
        "validation_positive_sign_by_split": [v > 0 for v in val_ret],
        "ranking": {
            "method": RANKING_ROLLING_ROBUSTNESS_V1,
            "w_dd": w_dd,
            "w_gap": w_gap,
            "w_frac": w_frac,
            "penalty_ineligible": penalty_ineligible,
        },
    }
    if has_test:
        agg["positive_test_splits"] = positive_test_splits
        agg["median_test_cumulative_return_pct"] = median_test_ret
        agg["frac_positive_test"] = frac_pos_test
    return score, agg


@dataclass
class _ScoredAggregate:
    params_key: str
    params: dict[str, Any]
    score: float
    aggregate: dict[str, Any]


def run_rolling_robustness_evaluation(
    db: Session,
    *,
    overall_start: date,
    overall_end: date,
    train_months: int,
    validate_months: int,
    test_months: int | None,
    step_months: int,
    source_payload: dict[str, Any],
    settings: Settings | None = None,
) -> LeaderFollowerRobustnessRun:
    """Execute rolling robustness run; persists splits, aggregates; commits session."""
    st = settings or get_settings()
    max_grid = st.leader_follower_optimization_max_grid_points
    max_work = st.leader_follower_robustness_max_evaluations

    try:
        splits = generate_monthly_rolling_splits(
            overall_start,
            overall_end,
            train_months=train_months,
            validate_months=validate_months,
            test_months=test_months,
            step_months=step_months,
        )
    except RollingSplitValidationError as exc:
        raise RollingRobustnessValidationError(str(exc)) from exc

    candidates, ranking, snapshot = load_rolling_source_payload(
        source_payload,
        max_grid_points=max_grid,
    )
    work_units = len(splits) * len(candidates)
    if work_units > max_work:
        raise RollingRobustnessValidationError(
            f"Work size splits×candidates={work_units} exceeds max {max_work}; "
            "reduce windows, step, grid/candidates, or raise leader_follower_robustness_max_evaluations."
        )

    has_test = splits[0].test_end is not None
    stored_config: dict[str, Any] = {
        "rolling": {
            "overall_start": overall_start.isoformat(),
            "overall_end": overall_end.isoformat(),
            "train_months": train_months,
            "validate_months": validate_months,
            "test_months": test_months,
            "step_months": step_months,
            "split_count": len(splits),
        },
        **snapshot,
        "grid_points_evaluated": len(candidates),
        "work_units": work_units,
    }

    run_row = LeaderFollowerRobustnessRun(
        overall_start=overall_start,
        overall_end=overall_end,
        train_window_spec=json.dumps({"unit": "months", "value": train_months}),
        validate_window_spec=json.dumps({"unit": "months", "value": validate_months}),
        test_window_spec=json.dumps({"unit": "months", "value": test_months}) if test_months else None,
        step_spec=json.dumps({"unit": "months", "value": step_months}),
        split_count=len(splits),
        grid_config_json=json.dumps(stored_config, sort_keys=True),
        ranking_method=str(ranking.get("method", RANKING_ROLLING_ROBUSTNESS_V1)),
    )
    run_repo = LeaderFollowerRobustnessRunRepository(db)
    run_repo.add(run_row)
    db.flush()

    per_params_metrics: dict[
        str, list[tuple[PaperSimulationMetrics, PaperSimulationMetrics, PaperSimulationMetrics | None]]
    ] = defaultdict(list)
    params_by_key: dict[str, dict[str, Any]] = {}
    split_rows: list[LeaderFollowerRobustnessSplitResult] = []

    logger.info(
        "Rolling robustness: run_id=%s splits=%s candidates=%s work=%s",
        run_row.id,
        len(splits),
        len(candidates),
        work_units,
    )

    for sw in splits:
        for full_params in candidates:
            pkey = _canonical_params(full_params)
            params_by_key.setdefault(pkey, full_params)
            cfg = PaperTradingConfig.from_json_dict(full_params)
            tr = compute_paper_trading_metrics(db, sw.train_start, sw.train_end, cfg)
            va = compute_paper_trading_metrics(db, sw.validate_start, sw.validate_end, cfg)
            te: PaperSimulationMetrics | None
            if sw.test_start is not None and sw.test_end is not None:
                te = compute_paper_trading_metrics(db, sw.test_start, sw.test_end, cfg)
            else:
                te = None
            per_params_metrics[pkey].append((tr, va, te))

            ch = _params_hash(full_params)
            split_rows.append(
                LeaderFollowerRobustnessSplitResult(
                    run_id=run_row.id,
                    config_hash=ch,
                    params_json=pkey,
                    split_index=sw.split_index,
                    train_start=sw.train_start,
                    train_end=sw.train_end,
                    validate_start=sw.validate_start,
                    validate_end=sw.validate_end,
                    test_start=sw.test_start,
                    test_end=sw.test_end,
                    train_metrics_json=json.dumps(tr.to_json_dict(), sort_keys=True),
                    validate_metrics_json=json.dumps(va.to_json_dict(), sort_keys=True),
                    test_metrics_json=json.dumps(te.to_json_dict(), sort_keys=True) if te is not None else None,
                )
            )

    split_repo = LeaderFollowerRobustnessSplitResultRepository(db)
    if split_rows:
        split_repo.add_all(split_rows)
        db.flush()

    scored: list[_ScoredAggregate] = []
    for pkey in sorted(per_params_metrics.keys()):
        tuples = per_params_metrics[pkey]
        score, agg = _score_and_aggregate_metrics(tuples, ranking, has_test=has_test)
        scored.append(
            _ScoredAggregate(
                params_key=pkey,
                params=params_by_key[pkey],
                score=score,
                aggregate=agg,
            )
        )

    scored.sort(key=lambda s: (-s.score, s.params_key))

    agg_repo = LeaderFollowerRobustnessAggregateRepository(db)
    agg_rows: list[LeaderFollowerRobustnessAggregate] = []
    for rank_idx, item in enumerate(scored, start=1):
        agg_rows.append(
            LeaderFollowerRobustnessAggregate(
                run_id=run_row.id,
                config_hash=_params_hash(item.params),
                params_json=item.params_key,
                aggregate_metrics_json=json.dumps(item.aggregate, sort_keys=True),
                robustness_score=item.score,
                rank=rank_idx,
            )
        )
    if agg_rows:
        agg_repo.add_all(agg_rows)

    db.commit()
    db.refresh(run_row)
    return run_row
