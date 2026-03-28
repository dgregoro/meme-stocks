"""Read-only API for leader-follower walk-forward optimization runs."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.data.database import get_session
from backend.app.data.repositories.leader_follower_optimization_result_repo import (
    LeaderFollowerOptimizationResultRepository,
)
from backend.app.data.repositories.leader_follower_optimization_run_repo import (
    LeaderFollowerOptimizationRunRepository,
)
from backend.app.models.leader_follower_optimization_run import LeaderFollowerOptimizationRun
from backend.app.utils.api_errors import error_detail

router = APIRouter(prefix="/api/leader-follower/optimization", tags=["leader-follower-optimization"])


class OptimizationRunListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    train_start: str
    train_end: str
    validate_start: str
    validate_end: str
    test_start: str | None
    test_end: str | None
    ranking_method: str
    result_count: int


class OptimizationRunListResponse(BaseModel):
    runs: list[OptimizationRunListItem]


class OptimizationRunDetailResponse(BaseModel):
    id: int
    created_at: datetime
    train_start: str
    train_end: str
    validate_start: str
    validate_end: str
    test_start: str | None
    test_end: str | None
    ranking_method: str
    config: dict[str, Any]


class OptimizationTopResultItem(BaseModel):
    rank: int
    robustness_score: float
    params: dict[str, Any]
    train_metrics: dict[str, Any]
    validate_metrics: dict[str, Any]
    test_metrics: dict[str, Any] | None


class OptimizationTopResultsResponse(BaseModel):
    run_id: int
    results: list[OptimizationTopResultItem]


def _not_found() -> NoReturn:
    raise HTTPException(
        status_code=404,
        detail=error_detail("NOT_FOUND", "Optimization run not found"),
    )


def _json_obj(s: str | None) -> dict[str, Any] | None:
    if s is None:
        return None
    try:
        d = json.loads(s)
        return d if isinstance(d, dict) else {}
    except json.JSONDecodeError:
        return {}


def _get_run_or_404(db: Session, run_id: int) -> LeaderFollowerOptimizationRun:
    run = LeaderFollowerOptimizationRunRepository(db).get(run_id)
    if run is None:
        _not_found()
    return run


@router.get("/runs", response_model=OptimizationRunListResponse)
def list_runs(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
) -> OptimizationRunListResponse:
    run_repo = LeaderFollowerOptimizationRunRepository(db)
    rows = run_repo.list_recent(limit=limit)
    items: list[OptimizationRunListItem] = []
    for r in rows:
        n = run_repo.count_results_for_run(r.id)
        items.append(
            OptimizationRunListItem(
                id=r.id,
                created_at=r.created_at,
                train_start=r.train_start.isoformat(),
                train_end=r.train_end.isoformat(),
                validate_start=r.validate_start.isoformat(),
                validate_end=r.validate_end.isoformat(),
                test_start=r.test_start.isoformat() if r.test_start else None,
                test_end=r.test_end.isoformat() if r.test_end else None,
                ranking_method=r.ranking_method,
                result_count=n,
            )
        )
    return OptimizationRunListResponse(runs=items)


@router.get("/{run_id}", response_model=OptimizationRunDetailResponse)
def get_run(run_id: int, db: Session = Depends(get_session)) -> OptimizationRunDetailResponse:
    r = _get_run_or_404(db, run_id)
    try:
        cfg = json.loads(r.config_json)
        if not isinstance(cfg, dict):
            cfg = {}
    except json.JSONDecodeError:
        cfg = {}
    return OptimizationRunDetailResponse(
        id=r.id,
        created_at=r.created_at,
        train_start=r.train_start.isoformat(),
        train_end=r.train_end.isoformat(),
        validate_start=r.validate_start.isoformat(),
        validate_end=r.validate_end.isoformat(),
        test_start=r.test_start.isoformat() if r.test_start else None,
        test_end=r.test_end.isoformat() if r.test_end else None,
        ranking_method=r.ranking_method,
        config=cfg,
    )


@router.get("/{run_id}/top-results", response_model=OptimizationTopResultsResponse)
def top_results(
    run_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_session),
) -> OptimizationTopResultsResponse:
    _get_run_or_404(db, run_id)
    result_repo = LeaderFollowerOptimizationResultRepository(db)
    rows = result_repo.list_top_for_run(run_id, limit=limit)
    out: list[OptimizationTopResultItem] = []
    for row in rows:
        params = _json_obj(row.params_json) or {}
        tm = _json_obj(row.train_metrics_json) or {}
        vm = _json_obj(row.validate_metrics_json) or {}
        tsm = _json_obj(row.test_metrics_json)
        out.append(
            OptimizationTopResultItem(
                rank=row.rank,
                robustness_score=row.robustness_score,
                params=params,
                train_metrics=tm,
                validate_metrics=vm,
                test_metrics=tsm,
            )
        )
    return OptimizationTopResultsResponse(run_id=run_id, results=out)
