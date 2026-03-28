"""API for leader-follower paper trading simulation runs."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.data.database import get_session
from backend.app.data.repositories.leader_follower_paper_run_repo import LeaderFollowerPaperRunRepository
from backend.app.data.repositories.leader_follower_paper_trade_repo import LeaderFollowerPaperTradeRepository
from backend.app.models.leader_follower_paper_run import LeaderFollowerPaperRun
from backend.app.utils.api_errors import error_detail

router = APIRouter(prefix="/api/leader-follower/paper-trading", tags=["leader-follower-paper-trading"])


class PaperTradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    leader_symbol: str
    follower_symbol: str
    signal_date: str
    signal_id: int | None
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    holding_period_days: int
    gross_return_pct: float
    net_return_pct: float
    sector_etf_symbol: str | None = None
    sector_close: float | None = None
    sector_ma: float | None = None
    sector_rolling_return_pct: float | None = None
    sector_confirmation_passed: bool | None = None
    regime_benchmark_symbol: str | None = None
    regime_decision_date: str | None = None
    regime_benchmark_close: float | None = None
    regime_benchmark_ma: float | None = None
    regime_market_uptrend_passed: bool | None = None
    regime_volatility: float | None = None
    regime_low_volatility_passed: bool | None = None
    regime_sector_strength_passed: bool | None = None
    regime_filter_passed: bool | None = None


class PaperRunSummaryOut(BaseModel):
    id: int
    created_at: datetime
    start_date: str
    end_date: str
    total_trades: int
    skipped_count: int
    skipped_sector_confirmation_count: int = 0
    skipped_regime_filter_count: int = 0
    cumulative_return_pct: float
    max_drawdown_pct: float


class PaperRunListResponse(BaseModel):
    runs: list[PaperRunSummaryOut]


class PaperRunDetailResponse(BaseModel):
    id: int
    created_at: datetime
    config: dict[str, Any]
    start_date: str
    end_date: str
    total_trades: int
    skipped_count: int
    skipped_sector_confirmation_count: int = 0
    skipped_regime_filter_count: int = 0
    win_rate: float
    avg_return_pct: float
    cumulative_return_pct: float
    max_drawdown_pct: float
    trades: list[PaperTradeOut]
    trades_total: int
    offset: int
    limit: int


class EquityPoint(BaseModel):
    trade_index: int
    equity: float
    cumulative_return_pct: float


class EquityCurveResponse(BaseModel):
    run_id: int
    points: list[EquityPoint]


def _not_found() -> NoReturn:
    raise HTTPException(
        status_code=404,
        detail=error_detail("NOT_FOUND", "Paper trading run not found"),
    )


def _get_run_or_404(db: Session, run_id: int) -> LeaderFollowerPaperRun:
    run = LeaderFollowerPaperRunRepository(db).get(run_id)
    if run is None:
        _not_found()
    return run


@router.get("/runs", response_model=PaperRunListResponse)
def list_runs(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
) -> PaperRunListResponse:
    repo = LeaderFollowerPaperRunRepository(db)
    rows = repo.list_recent(limit=limit)
    runs = [
        PaperRunSummaryOut(
            id=r.id,
            created_at=r.created_at,
            start_date=r.start_date.isoformat(),
            end_date=r.end_date.isoformat(),
            total_trades=r.total_trades,
            skipped_count=r.skipped_count,
            skipped_sector_confirmation_count=r.skipped_sector_confirmation_count,
            skipped_regime_filter_count=r.skipped_regime_filter_count,
            cumulative_return_pct=r.cumulative_return_pct,
            max_drawdown_pct=r.max_drawdown_pct,
        )
        for r in rows
    ]
    return PaperRunListResponse(runs=runs)


@router.get("/{run_id}", response_model=PaperRunDetailResponse)
def get_run(
    run_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_session),
) -> PaperRunDetailResponse:
    trade_repo = LeaderFollowerPaperTradeRepository(db)
    run = _get_run_or_404(db, run_id)

    cfg: dict[str, Any]
    try:
        cfg = json.loads(run.config_json)
    except (json.JSONDecodeError, TypeError):
        cfg = {}

    total = trade_repo.count_for_run(run_id)
    trades = trade_repo.list_for_run(run_id, offset=offset, limit=limit)
    trades_out = [
        PaperTradeOut(
            id=t.id,
            leader_symbol=t.leader_symbol,
            follower_symbol=t.follower_symbol,
            signal_date=t.signal_date.isoformat(),
            signal_id=t.signal_id,
            entry_price=t.entry_price,
            exit_price=t.exit_price,
            entry_time=t.entry_time,
            exit_time=t.exit_time,
            holding_period_days=t.holding_period_days,
            gross_return_pct=t.gross_return_pct,
            net_return_pct=t.net_return_pct,
            sector_etf_symbol=t.sector_etf_symbol,
            sector_close=t.sector_close,
            sector_ma=t.sector_ma,
            sector_rolling_return_pct=t.sector_rolling_return_pct,
            sector_confirmation_passed=t.sector_confirmation_passed,
            regime_benchmark_symbol=t.regime_benchmark_symbol,
            regime_decision_date=t.regime_decision_date.isoformat() if t.regime_decision_date else None,
            regime_benchmark_close=t.regime_benchmark_close,
            regime_benchmark_ma=t.regime_benchmark_ma,
            regime_market_uptrend_passed=t.regime_market_uptrend_passed,
            regime_volatility=t.regime_volatility,
            regime_low_volatility_passed=t.regime_low_volatility_passed,
            regime_sector_strength_passed=t.regime_sector_strength_passed,
            regime_filter_passed=t.regime_filter_passed,
        )
        for t in trades
    ]

    return PaperRunDetailResponse(
        id=run.id,
        created_at=run.created_at,
        config=cfg,
        start_date=run.start_date.isoformat(),
        end_date=run.end_date.isoformat(),
        total_trades=run.total_trades,
        skipped_count=run.skipped_count,
        skipped_sector_confirmation_count=run.skipped_sector_confirmation_count,
        skipped_regime_filter_count=run.skipped_regime_filter_count,
        win_rate=run.win_rate,
        avg_return_pct=run.avg_return_pct,
        cumulative_return_pct=run.cumulative_return_pct,
        max_drawdown_pct=run.max_drawdown_pct,
        trades=trades_out,
        trades_total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{run_id}/equity-curve", response_model=EquityCurveResponse)
def get_equity_curve(
    run_id: int,
    db: Session = Depends(get_session),
) -> EquityCurveResponse:
    trade_repo = LeaderFollowerPaperTradeRepository(db)
    _get_run_or_404(db, run_id)

    ordered = trade_repo.list_all_for_run_ordered(run_id)
    points: list[EquityPoint] = []
    equity = 1.0
    for i, t in enumerate(ordered):
        equity *= 1.0 + t.net_return_pct / 100.0
        cum_pct = (equity - 1.0) * 100.0
        points.append(
            EquityPoint(
                trade_index=i,
                equity=equity,
                cumulative_return_pct=cum_pct,
            )
        )

    return EquityCurveResponse(run_id=run_id, points=points)
