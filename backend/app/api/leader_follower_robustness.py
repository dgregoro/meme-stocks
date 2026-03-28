"""Read-only API for leader-follower rolling robustness runs."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.data.database import get_session
from backend.app.data.repositories.leader_follower_robustness_aggregate_repo import (
    LeaderFollowerRobustnessAggregateRepository,
)
from backend.app.data.repositories.leader_follower_robustness_run_repo import (
    LeaderFollowerRobustnessRunRepository,
)
from backend.app.data.repositories.leader_follower_robustness_split_result_repo import (
    LeaderFollowerRobustnessSplitResultRepository,
)
from backend.app.models.leader_follower_robustness_run import LeaderFollowerRobustnessRun
from backend.app.utils.api_errors import error_detail

router = APIRouter(prefix="/api/leader-follower/robustness", tags=["leader-follower-robustness"])


class RobustnessRunListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    overall_start: str
    overall_end: str
    split_count: int
    ranking_method: str
    split_result_row_count: int
    aggregate_count: int


class RobustnessRunListResponse(BaseModel):
    runs: list[RobustnessRunListItem]


class RobustnessRunDetailResponse(BaseModel):
    id: int
    created_at: datetime
    overall_start: str
    overall_end: str
    split_count: int
    train_window_spec: str
    validate_window_spec: str
    test_window_spec: str | None
    step_spec: str
    ranking_method: str
    config: dict[str, Any]


class RobustnessTopResultItem(BaseModel):
    rank: int
    robustness_score: float
    params: dict[str, Any]
    aggregate_metrics: dict[str, Any]


class RobustnessTopResultsResponse(BaseModel):
    run_id: int
    results: list[RobustnessTopResultItem]


class RobustnessSplitItem(BaseModel):
    split_index: int
    config_hash: str | None
    params: dict[str, Any]
    train_start: str
    train_end: str
    validate_start: str
    validate_end: str
    test_start: str | None
    test_end: str | None
    train_metrics: dict[str, Any]
    validate_metrics: dict[str, Any]
    test_metrics: dict[str, Any] | None


class RobustnessSplitsResponse(BaseModel):
    run_id: int
    items: list[RobustnessSplitItem]


def _not_found() -> NoReturn:
    raise HTTPException(
        status_code=404,
        detail=error_detail("NOT_FOUND", "Robustness run not found"),
    )


def _json_obj(s: str | None) -> dict[str, Any] | None:
    if s is None:
        return None
    try:
        d = json.loads(s)
        return d if isinstance(d, dict) else {}
    except json.JSONDecodeError:
        return {}


def _get_run_or_404(db: Session, run_id: int) -> LeaderFollowerRobustnessRun:
    run = LeaderFollowerRobustnessRunRepository(db).get(run_id)
    if run is None:
        _not_found()
    return run


@router.get("/runs", response_model=RobustnessRunListResponse)
def list_runs(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
) -> RobustnessRunListResponse:
    run_repo = LeaderFollowerRobustnessRunRepository(db)
    rows = run_repo.list_recent(limit=limit)
    items: list[RobustnessRunListItem] = []
    for r in rows:
        items.append(
            RobustnessRunListItem(
                id=r.id,
                created_at=r.created_at,
                overall_start=r.overall_start.isoformat(),
                overall_end=r.overall_end.isoformat(),
                split_count=r.split_count,
                ranking_method=r.ranking_method,
                split_result_row_count=run_repo.count_split_results_for_run(r.id),
                aggregate_count=run_repo.count_aggregates_for_run(r.id),
            )
        )
    return RobustnessRunListResponse(runs=items)


@router.get("/{run_id}", response_model=RobustnessRunDetailResponse)
def get_run(run_id: int, db: Session = Depends(get_session)) -> RobustnessRunDetailResponse:
    r = _get_run_or_404(db, run_id)
    try:
        cfg = json.loads(r.grid_config_json)
        if not isinstance(cfg, dict):
            cfg = {}
    except json.JSONDecodeError:
        cfg = {}
    return RobustnessRunDetailResponse(
        id=r.id,
        created_at=r.created_at,
        overall_start=r.overall_start.isoformat(),
        overall_end=r.overall_end.isoformat(),
        split_count=r.split_count,
        train_window_spec=r.train_window_spec,
        validate_window_spec=r.validate_window_spec,
        test_window_spec=r.test_window_spec,
        step_spec=r.step_spec,
        ranking_method=r.ranking_method,
        config=cfg,
    )


@router.get("/{run_id}/top-results", response_model=RobustnessTopResultsResponse)
def top_results(
    run_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_session),
) -> RobustnessTopResultsResponse:
    _get_run_or_404(db, run_id)
    agg_repo = LeaderFollowerRobustnessAggregateRepository(db)
    rows = agg_repo.list_top_for_run(run_id, limit=limit)
    out: list[RobustnessTopResultItem] = []
    for row in rows:
        params = _json_obj(row.params_json) or {}
        am = _json_obj(row.aggregate_metrics_json) or {}
        out.append(
            RobustnessTopResultItem(
                rank=row.rank,
                robustness_score=row.robustness_score,
                params=params,
                aggregate_metrics=am,
            )
        )
    return RobustnessTopResultsResponse(run_id=run_id, results=out)


@router.get("/{run_id}/splits", response_model=RobustnessSplitsResponse)
def list_splits(
    run_id: int,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    config_key: str | None = Query(
        None,
        description="SHA-256 hex of canonical params (matches config_hash)",
    ),
    split_index: int | None = Query(None, ge=0),
    db: Session = Depends(get_session),
) -> RobustnessSplitsResponse:
    _get_run_or_404(db, run_id)
    split_repo = LeaderFollowerRobustnessSplitResultRepository(db)
    rows = split_repo.list_for_run(
        run_id,
        limit=limit,
        offset=offset,
        config_hash=config_key,
        split_index=split_index,
    )
    items: list[RobustnessSplitItem] = []
    for row in rows:
        params = _json_obj(row.params_json) or {}
        tm = _json_obj(row.train_metrics_json) or {}
        vm = _json_obj(row.validate_metrics_json) or {}
        tsm = _json_obj(row.test_metrics_json)
        items.append(
            RobustnessSplitItem(
                split_index=row.split_index,
                config_hash=row.config_hash,
                params=params,
                train_start=row.train_start.isoformat(),
                train_end=row.train_end.isoformat(),
                validate_start=row.validate_start.isoformat(),
                validate_end=row.validate_end.isoformat(),
                test_start=row.test_start.isoformat() if row.test_start else None,
                test_end=row.test_end.isoformat() if row.test_end else None,
                train_metrics=tm,
                validate_metrics=vm,
                test_metrics=tsm,
            )
        )
    return RobustnessSplitsResponse(run_id=run_id, items=items)
