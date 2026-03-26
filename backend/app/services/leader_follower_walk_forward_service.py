"""Walk-forward optimization over paper-trading parameters (research tooling)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from itertools import product
from typing import Any

from sqlalchemy.orm import Session

from backend.app.config import Settings, get_settings
from backend.app.data.repositories.leader_follower_optimization_result_repo import (
    LeaderFollowerOptimizationResultRepository,
)
from backend.app.data.repositories.leader_follower_optimization_run_repo import (
    LeaderFollowerOptimizationRunRepository,
)
from backend.app.models.leader_follower_optimization_result import LeaderFollowerOptimizationResult
from backend.app.models.leader_follower_optimization_run import LeaderFollowerOptimizationRun
from backend.app.services.leader_follower_paper_trading_service import (
    PaperTradingConfig,
    PaperSimulationMetrics,
    compute_paper_trading_metrics,
)

RANKING_WALK_FORWARD_V1 = "walk_forward_v1"

ALLOWED_GRID_KEYS = frozenset(
    {
        "holding_days",
        "max_positions_per_event",
        "min_pair_score",
        "entry_mode",
        "exit_mode",
        "per_trade_cost_pct",
    }
)

DEFAULT_GRID_FILE_PAYLOAD: dict[str, Any] = {
    "base_config": {
        "entry_mode": "next_open",
        "exit_mode": "fixed_days",
        "per_trade_cost_pct": 0.1,
    },
    "grid": {
        "holding_days": [1, 3, 5],
        "max_positions_per_event": [1, 2],
    },
    "ranking": {
        "method": RANKING_WALK_FORWARD_V1,
        "min_trades_validate": 5,
        "w_deg": 0.5,
        "w_dd": 0.25,
    },
}


class WalkForwardValidationError(ValueError):
    """Invalid date windows or grid configuration."""


def validate_walk_forward_windows(
    train_start: date,
    train_end: date,
    validate_start: date,
    validate_end: date,
    test_start: date | None,
    test_end: date | None,
) -> None:
    if train_start > train_end:
        raise WalkForwardValidationError("train_start must be <= train_end")
    if validate_start > validate_end:
        raise WalkForwardValidationError("validate_start must be <= validate_end")
    if train_end >= validate_start:
        raise WalkForwardValidationError("train period must end before validate_start")

    if test_start is not None and test_end is not None:
        if test_start > test_end:
            raise WalkForwardValidationError("test_start must be <= test_end")
        if validate_end >= test_start:
            raise WalkForwardValidationError("validate must end before test_start")
        overlap_test_train = not (test_end < train_start or train_end < test_start)
        overlap_test_val = not (test_end < validate_start or validate_end < test_start)
        if overlap_test_train or overlap_test_val:
            raise WalkForwardValidationError("test window must not overlap train or validate")
    elif test_start is not None or test_end is not None:
        raise WalkForwardValidationError("test_start and test_end must both be set or both omitted")


def _merge_ranking_defaults(ranking: dict[str, Any]) -> dict[str, Any]:
    out = dict(DEFAULT_GRID_FILE_PAYLOAD["ranking"])
    out.update(ranking)
    return out


def load_grid_config_from_dict(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize loaded JSON: base_config, grid, ranking."""
    base = dict(raw.get("base_config") or {})
    grid = raw.get("grid")
    if not isinstance(grid, dict) or not grid:
        raise WalkForwardValidationError("grid must be a non-empty object")
    ranking = _merge_ranking_defaults(dict(raw.get("ranking") or {}))

    unknown = set(grid.keys()) - ALLOWED_GRID_KEYS
    if unknown:
        raise WalkForwardValidationError(f"Unsupported grid keys: {sorted(unknown)}")

    for key, values in grid.items():
        if not isinstance(values, list) or len(values) == 0:
            raise WalkForwardValidationError(f"grid.{key} must be a non-empty list")

    method = ranking.get("method")
    if method != RANKING_WALK_FORWARD_V1:
        raise WalkForwardValidationError(f"Unsupported ranking method: {method!r}")

    return {"base_config": base, "grid": grid, "ranking": ranking}


def expand_grid_points(grid_cfg: dict[str, Any], max_combinations: int) -> list[dict[str, Any]]:
    grid = grid_cfg["grid"]
    keys = sorted(grid.keys())
    value_lists = [grid[k] for k in keys]
    n = 1
    for vl in value_lists:
        n *= len(vl)
    if n > max_combinations:
        raise WalkForwardValidationError(
            f"Grid has {n} combinations; max allowed is {max_combinations}. Reduce the grid."
        )

    out: list[dict[str, Any]] = []
    for combo in product(*value_lists):
        out.append(dict(zip(keys, combo, strict=True)))
    return out


def _build_paper_config(base: dict[str, Any], point: dict[str, Any]) -> PaperTradingConfig:
    merged = dict(base)
    merged.update(point)
    return PaperTradingConfig.from_json_dict(merged)


def robustness_walk_forward_v1(
    train: PaperSimulationMetrics,
    validate: PaperSimulationMetrics,
    *,
    min_trades_validate: int,
    w_deg: float,
    w_dd: float,
) -> float:
    """Validation-first score; penalize train>validate gap and drawdown. See specs/research.md."""
    v_n = validate.total_trades
    if v_n < min_trades_validate:
        return -10000.0 + float(v_n)

    v = validate.cumulative_return_pct
    t = train.cumulative_return_pct
    d = validate.max_drawdown_pct
    return float(v) - w_deg * max(0.0, t - v) - w_dd * float(d)


@dataclass
class _EvaluatedPoint:
    params: dict[str, Any]
    train: PaperSimulationMetrics
    validate: PaperSimulationMetrics
    test: PaperSimulationMetrics | None
    score: float


def run_walk_forward_optimization(
    db: Session,
    *,
    train_start: date,
    train_end: date,
    validate_start: date,
    validate_end: date,
    test_start: date | None,
    test_end: date | None,
    grid_payload: dict[str, Any],
    settings: Settings | None = None,
) -> LeaderFollowerOptimizationRun:
    """Execute full walk-forward run; persist run and ranked results. Commits the session."""
    st = settings or get_settings()
    validate_walk_forward_windows(
        train_start, train_end, validate_start, validate_end, test_start, test_end
    )
    normalized = load_grid_config_from_dict(grid_payload)
    base_config = normalized["base_config"]
    ranking = normalized["ranking"]

    points = expand_grid_points(normalized, st.leader_follower_optimization_max_grid_points)

    min_trades = int(ranking.get("min_trades_validate", 5))
    w_deg = float(ranking.get("w_deg", 0.5))
    w_dd = float(ranking.get("w_dd", 0.25))

    evaluated: list[_EvaluatedPoint] = []
    for point in points:
        cfg = _build_paper_config(base_config, point)
        tr = compute_paper_trading_metrics(db, train_start, train_end, cfg)
        va = compute_paper_trading_metrics(db, validate_start, validate_end, cfg)
        te: PaperSimulationMetrics | None = None
        if test_start is not None and test_end is not None:
            te = compute_paper_trading_metrics(db, test_start, test_end, cfg)
        score = robustness_walk_forward_v1(
            tr,
            va,
            min_trades_validate=min_trades,
            w_deg=w_deg,
            w_dd=w_dd,
        )
        params_full = {**base_config, **point}
        evaluated.append(
            _EvaluatedPoint(
                params=params_full,
                train=tr,
                validate=va,
                test=te,
                score=score,
            )
        )

    evaluated.sort(
        key=lambda e: (-e.score, json.dumps(e.params, sort_keys=True)),
    )

    stored_config: dict[str, Any] = {
        "windows": {
            "train_start": train_start.isoformat(),
            "train_end": train_end.isoformat(),
            "validate_start": validate_start.isoformat(),
            "validate_end": validate_end.isoformat(),
            "test_start": test_start.isoformat() if test_start else None,
            "test_end": test_end.isoformat() if test_end else None,
        },
        "base_config": normalized["base_config"],
        "grid": normalized["grid"],
        "ranking": normalized["ranking"],
        "grid_points_evaluated": len(points),
        "ranking_applied": ranking,
    }

    run_row = LeaderFollowerOptimizationRun(
        config_json=json.dumps(stored_config, sort_keys=True),
        train_start=train_start,
        train_end=train_end,
        validate_start=validate_start,
        validate_end=validate_end,
        test_start=test_start,
        test_end=test_end,
        ranking_method=str(ranking.get("method", RANKING_WALK_FORWARD_V1)),
    )
    run_repo = LeaderFollowerOptimizationRunRepository(db)
    run_repo.add(run_row)
    db.flush()

    result_repo = LeaderFollowerOptimizationResultRepository(db)
    result_rows: list[LeaderFollowerOptimizationResult] = []
    for rank_idx, ev in enumerate(evaluated, start=1):
        test_json = (
            json.dumps(ev.test.to_json_dict(), sort_keys=True) if ev.test is not None else None
        )
        result_rows.append(
            LeaderFollowerOptimizationResult(
                run_id=run_row.id,
                params_json=json.dumps(ev.params, sort_keys=True),
                train_metrics_json=json.dumps(ev.train.to_json_dict(), sort_keys=True),
                validate_metrics_json=json.dumps(ev.validate.to_json_dict(), sort_keys=True),
                test_metrics_json=test_json,
                robustness_score=ev.score,
                rank=rank_idx,
            )
        )
    if result_rows:
        result_repo.add_all(result_rows)
    db.commit()
    db.refresh(run_row)
    return run_row


def read_optimization_grid_file(path: str) -> dict[str, Any]:
    """Load raw JSON object from path; caller passes result to ``run_walk_forward_optimization``."""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise WalkForwardValidationError("Grid file must contain a JSON object")
    return raw
