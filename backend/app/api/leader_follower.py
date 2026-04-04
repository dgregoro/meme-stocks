"""Leader-follower signals API."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.data.database import get_session
from backend.app.data.repositories.job_execution_repo import JobExecutionRepository
from backend.app.data.repositories.leader_debug_repo import LeaderDebugRepository
from backend.app.data.repositories.leader_event_repo import LeaderEventRepository
from backend.app.data.repositories.leader_follower_candidate_repo import LeaderFollowerCandidateRepository
from backend.app.data.repositories.leader_follower_signal_repo import LeaderFollowerSignalRepository
from backend.app.config import get_settings
from backend.app.services.leader_follower_evaluation_service import (
    aggregate_by_pair,
    aggregate_summary,
    evaluate_signal,
    filter_pairs_by_thresholds,
    rank_pairs,
    run_evaluation,
)
from backend.app.services.leader_follower_replay_service import LEADER_FOLLOWER_REPLAY_JOB_NAME

router = APIRouter(prefix="/api/leader-follower", tags=["leader-follower"])

LEADER_FOLLOWER_JOB = "leader_follower_detection"
LEADER_FOLLOWER_RUN_JOB_NAMES = (LEADER_FOLLOWER_JOB, LEADER_FOLLOWER_REPLAY_JOB_NAME)

EmptyReason = Literal["no_run", "failed", "stock_groups_empty", "no_leaders", "no_candidates", "no_confirmations", "ok"]


def _derive_empty_reason(
    last_run: Any | None,
    metrics: dict[str, Any] | None,
) -> EmptyReason:
    """Derive empty_reason from last run and metrics. Use when signals=[] to explain why."""
    if last_run is None:
        return "no_run"
    if getattr(last_run, "success", True) is False:
        return "failed"
    if metrics is None:
        return "ok"  # No metrics to infer; treat as ok
    grouped_size = metrics.get("grouped_leader_universe_size", 0) or 0
    leaders = metrics.get("leader_events_detected", 0) or 0
    candidates = metrics.get("follower_candidates_found", 0) or 0
    signals = metrics.get("signals_emitted", 0) or 0
    if grouped_size == 0:
        return "stock_groups_empty"
    if leaders == 0:
        return "no_leaders"
    if candidates == 0:
        return "no_candidates"
    if signals == 0:
        return "no_confirmations"
    return "ok"


def _as_utc_aware(dt: datetime | None) -> datetime | None:
    """Normalize datetime to UTC-aware; treat naive as UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_metrics(metrics_json: str | None) -> dict[str, Any] | None:
    """Parse metrics_json; return None on failure."""
    if not metrics_json:
        return None
    try:
        return json.loads(metrics_json)
    except (json.JSONDecodeError, TypeError):
        return None


class LastRunInfo(BaseModel):
    """Most recent run summary for status."""

    run_id: int
    run_at: str
    started_at: str
    duration_seconds: float | None
    success: bool
    error_message: str | None
    summary: str | None


class StageCounts(BaseModel):
    """Pipeline stage counts from metrics_json."""

    input_universe_size: int = 0
    grouped_leader_universe_size: int = 0
    leader_events_detected: int = 0
    follower_candidates_found: int = 0
    signals_emitted: int = 0


class StatusResponse(BaseModel):
    """Response for GET /status."""

    last_run: LastRunInfo | None
    stage_counts: StageCounts | None
    empty_reason: EmptyReason


@router.get("/status", response_model=StatusResponse)
def get_status(db: Session = Depends(get_session)) -> StatusResponse:
    """One-stop diagnostic: last run, stage counts, empty_reason."""
    job_repo = JobExecutionRepository(db)
    runs = job_repo.list_recent_runs(limit=1, job_names=LEADER_FOLLOWER_RUN_JOB_NAMES)
    last_run = runs[0] if runs else None

    if last_run is None:
        return StatusResponse(
            last_run=None,
            stage_counts=None,
            empty_reason="no_run",
        )

    metrics = _parse_metrics(getattr(last_run, "metrics_json", None))
    empty_reason = _derive_empty_reason(last_run, metrics)

    run_at = _as_utc_aware(last_run.run_at)
    started_at = _as_utc_aware(last_run.started_at)
    last_run_info = LastRunInfo(
        run_id=last_run.id,
        run_at=run_at.isoformat() if run_at else "",
        started_at=started_at.isoformat() if started_at else "",
        duration_seconds=last_run.duration_seconds,
        success=last_run.success,
        error_message=last_run.error_message,
        summary=getattr(last_run, "summary", None),
    )

    stage_counts = (
        StageCounts(
            input_universe_size=int(metrics.get("input_universe_size", 0) or 0),
            grouped_leader_universe_size=int(metrics.get("grouped_leader_universe_size", 0) or 0),
            leader_events_detected=int(metrics.get("leader_events_detected", 0) or 0),
            follower_candidates_found=int(metrics.get("follower_candidates_found", 0) or 0),
            signals_emitted=int(metrics.get("signals_emitted", 0) or 0),
        )
        if metrics
        else StageCounts()
    )

    return StatusResponse(
        last_run=last_run_info,
        stage_counts=stage_counts,
        empty_reason=empty_reason,
    )


class RunItem(BaseModel):
    """Single job run for GET /runs."""

    id: int
    run_at: str
    started_at: str
    duration_seconds: float | None
    success: bool
    error_message: str | None
    summary: str | None
    metrics: dict[str, Any] = {}


class RunsResponse(BaseModel):
    """Response for GET /runs."""

    runs: list[RunItem]


@router.get("/runs", response_model=RunsResponse)
def list_runs(
    db: Session = Depends(get_session),
    limit: int = Query(20, ge=1, le=100),
    since_date: date | None = Query(None, description="Filter runs on or after this date (run_at)"),
    until_date: date | None = Query(None, description="Filter runs on or before this date"),
) -> RunsResponse:
    """Recent job runs with full metrics for leader-follower detection."""
    job_repo = JobExecutionRepository(db)
    runs = job_repo.list_recent_runs(
        limit=limit,
        since_date=since_date,
        until_date=until_date,
        job_names=LEADER_FOLLOWER_RUN_JOB_NAMES,
    )
    items = []
    for h in runs:
        run_at = _as_utc_aware(h.run_at)
        started_at = _as_utc_aware(h.started_at)
        metrics = _parse_metrics(getattr(h, "metrics_json", None)) or {}
        items.append(
            RunItem(
                id=h.id,
                run_at=run_at.isoformat() if run_at else "",
                started_at=started_at.isoformat() if started_at else "",
                duration_seconds=h.duration_seconds,
                success=h.success,
                error_message=h.error_message,
                summary=getattr(h, "summary", None),
                metrics=metrics,
            )
        )
    return RunsResponse(runs=items)


class LeaderEventItem(BaseModel):
    """Single leader event for GET /leader-events."""

    id: int
    leader_symbol: str
    event_date: str
    return_pct: float
    volume_ratio: float
    direction: str
    run_id: int | None
    created_at: str


class LeaderEventsResponse(BaseModel):
    """Response for GET /leader-events."""

    events: list[LeaderEventItem]


@router.get("/leader-events", response_model=LeaderEventsResponse)
def list_leader_events(
    db: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
    since_date: date | None = Query(None),
    leader: str | None = Query(None),
    run_id: int | None = Query(None),
) -> LeaderEventsResponse:
    """Recent leader events with optional filters."""
    repo = LeaderEventRepository(db)
    events = repo.list_recent(limit=limit, since_date=since_date, leader=leader, run_id=run_id)
    items = []
    for e in events:
        created_at = e.created_at
        if isinstance(created_at, datetime) and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        items.append(
            LeaderEventItem(
                id=e.id,
                leader_symbol=e.leader_symbol,
                event_date=e.event_date.isoformat() if hasattr(e.event_date, "isoformat") else str(e.event_date),
                return_pct=e.return_pct,
                volume_ratio=e.volume_ratio,
                direction=e.direction,
                run_id=getattr(e, "job_run_id", None),
                created_at=created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
            )
        )
    return LeaderEventsResponse(events=items)


class FollowerCandidateItem(BaseModel):
    """Single follower candidate for GET /follower-candidates."""

    leader_symbol: str
    follower_symbol: str
    event_date: str
    group_id: str
    run_id: int
    metrics: dict[str, Any] = {}
    created_at: str


class FollowerCandidatesResponse(BaseModel):
    """Response for GET /follower-candidates."""

    candidates: list[FollowerCandidateItem]


@router.get("/follower-candidates", response_model=FollowerCandidatesResponse)
def list_follower_candidates(
    db: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
    since_date: date | None = Query(None),
    leader: str | None = Query(None),
    follower: str | None = Query(None),
    run_id: int | None = Query(None),
) -> FollowerCandidatesResponse:
    """Recent follower candidates with optional filters."""
    repo = LeaderFollowerCandidateRepository(db)
    candidates = repo.list_recent(
        limit=limit,
        since_date=since_date,
        leader=leader,
        follower=follower,
        run_id=run_id,
    )
    items = []
    for c in candidates:
        metrics: dict[str, Any] = {}
        if c.metrics_json:
            try:
                metrics = json.loads(c.metrics_json)
            except (json.JSONDecodeError, TypeError):
                pass
        created_at = c.created_at
        if isinstance(created_at, datetime) and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        items.append(
            FollowerCandidateItem(
                leader_symbol=c.leader_symbol,
                follower_symbol=c.follower_symbol,
                event_date=c.event_date.isoformat() if hasattr(c.event_date, "isoformat") else str(c.event_date),
                group_id=c.group_id,
                run_id=c.job_run_id,
                metrics=metrics,
                created_at=created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
            )
        )
    return FollowerCandidatesResponse(candidates=items)


class SignalItem(BaseModel):
    """Single leader-follower signal."""

    id: int
    leader_symbol: str
    follower_symbol: str
    group_id: str
    signal_date: str
    strength_score: float
    leader_return_pct: float
    leader_volume_ratio: float
    metrics: dict[str, Any] = {}
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class SignalsDiagnostics(BaseModel):
    """Diagnostics block when signals=[] to explain why empty."""

    last_run_id: int | None
    last_run_at: str | None
    stage_counts: StageCounts | None
    empty_reason: EmptyReason


class SignalsResponse(BaseModel):
    """Response for GET /signals."""

    signals: list[SignalItem]
    diagnostics: SignalsDiagnostics | None = None


def _signal_to_item(signal: Any) -> SignalItem:
    """Convert ORM signal to response item."""
    import json

    metrics: dict[str, Any] = {}
    if signal.metrics_json:
        try:
            metrics = json.loads(signal.metrics_json)
        except (json.JSONDecodeError, TypeError):
            pass
    created_at = signal.created_at
    if isinstance(created_at, datetime) and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return SignalItem(
        id=signal.id,
        leader_symbol=signal.leader_symbol,
        follower_symbol=signal.follower_symbol,
        group_id=signal.group_id,
        signal_date=(
            signal.signal_date.isoformat() if hasattr(signal.signal_date, "isoformat") else str(signal.signal_date)
        ),
        strength_score=signal.strength_score,
        leader_return_pct=signal.leader_return_pct,
        leader_volume_ratio=signal.leader_volume_ratio,
        metrics=metrics,
        created_at=created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
    )


def _build_signals_diagnostics(db: Session) -> SignalsDiagnostics:
    """Build diagnostics from last run for empty signals case."""
    job_repo = JobExecutionRepository(db)
    runs = job_repo.list_recent_runs(limit=1, job_names=LEADER_FOLLOWER_RUN_JOB_NAMES)
    last_run = runs[0] if runs else None

    if last_run is None:
        return SignalsDiagnostics(
            last_run_id=None,
            last_run_at=None,
            stage_counts=None,
            empty_reason="no_run",
        )

    metrics = _parse_metrics(getattr(last_run, "metrics_json", None))
    empty_reason = _derive_empty_reason(last_run, metrics)

    run_at = _as_utc_aware(last_run.run_at)
    last_run_at_str = run_at.isoformat() if run_at else None

    stage_counts = None
    if metrics:
        stage_counts = StageCounts(
            input_universe_size=metrics.get("input_universe_size", 0) or 0,
            grouped_leader_universe_size=metrics.get("grouped_leader_universe_size", 0) or 0,
            leader_events_detected=metrics.get("leader_events_detected", 0) or 0,
            follower_candidates_found=metrics.get("follower_candidates_found", 0) or 0,
            signals_emitted=metrics.get("signals_emitted", 0) or 0,
        )

    return SignalsDiagnostics(
        last_run_id=last_run.id,
        last_run_at=last_run_at_str,
        stage_counts=stage_counts,
        empty_reason=empty_reason,
    )


class EvaluationItem(BaseModel):
    """Single evaluation for GET /leader-debug."""

    symbol: str
    return_pct: float | None
    volume_ratio: float | None
    qualified_as_leader: bool
    rejection_reasons: list[str]


class LeaderDebugResponse(BaseModel):
    """Response for GET /leader-debug."""

    run_id: int
    event_date: str
    evaluated_count: int
    leaders_count: int
    evaluations: list[EvaluationItem]


@router.get("/leader-debug", response_model=LeaderDebugResponse)
def get_leader_debug(
    db: Session = Depends(get_session),
    run_id: int = Query(..., description="Job run ID from job_run_history"),
    limit: int = Query(50, ge=1, le=200),
) -> LeaderDebugResponse:
    """Symbol-level evaluation data for a given run. Returns 404 if run does not exist."""
    job_repo = JobExecutionRepository(db)
    run = job_repo.get_run_by_id(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    metrics = _parse_metrics(getattr(run, "metrics_json", None))
    run_at = _as_utc_aware(run.run_at)
    event_date_str = (metrics.get("event_date") if metrics else None) or (run_at.date().isoformat() if run_at else "")
    debug_repo = LeaderDebugRepository(db)
    evals = debug_repo.list_by_run_id(run_id, limit=limit)
    leaders_count = sum(1 for e in evals if e.qualified_as_leader)
    items = []
    for e in evals:
        reasons: list[str] = []
        if e.rejection_reasons:
            try:
                reasons = json.loads(e.rejection_reasons)
            except (json.JSONDecodeError, TypeError):
                pass
        items.append(
            EvaluationItem(
                symbol=e.stock_symbol,
                return_pct=e.return_pct,
                volume_ratio=e.volume_ratio,
                qualified_as_leader=e.qualified_as_leader,
                rejection_reasons=reasons,
            )
        )
    return LeaderDebugResponse(
        run_id=run_id,
        event_date=event_date_str,
        evaluated_count=len(items),
        leaders_count=leaders_count,
        evaluations=items,
    )


class NearMissItem(BaseModel):
    """Single near-miss for GET /leader-near-miss."""

    symbol: str
    return_pct: float
    volume_ratio: float
    rejection_reasons: list[str]
    return_threshold: float | None = None
    volume_threshold: float | None = None


class LeaderNearMissResponse(BaseModel):
    """Response for GET /leader-near-miss."""

    run_id: int
    near_misses: list[NearMissItem]


@router.get("/leader-near-miss", response_model=LeaderNearMissResponse)
def get_leader_near_miss(
    db: Session = Depends(get_session),
    run_id: int = Query(..., description="Job run ID"),
    limit: int = Query(20, ge=1, le=100),
) -> LeaderNearMissResponse:
    """Top near-miss symbols for a run. Returns 404 if run does not exist."""
    job_repo = JobExecutionRepository(db)
    run = job_repo.get_run_by_id(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    debug_repo = LeaderDebugRepository(db)
    near_misses = debug_repo.list_near_misses_by_run_id(run_id, limit=limit)
    items = []
    for e in near_misses:
        reasons: list[str] = []
        if e.rejection_reasons:
            try:
                reasons = json.loads(e.rejection_reasons)
            except (json.JSONDecodeError, TypeError):
                pass
        metrics: dict[str, Any] = {}
        if e.metrics_json:
            try:
                metrics = json.loads(e.metrics_json)
            except (json.JSONDecodeError, TypeError):
                pass
        items.append(
            NearMissItem(
                symbol=e.stock_symbol,
                return_pct=e.return_pct or 0.0,
                volume_ratio=e.volume_ratio or 0.0,
                rejection_reasons=reasons,
                return_threshold=metrics.get("return_threshold"),
                volume_threshold=metrics.get("volume_threshold"),
            )
        )
    return LeaderNearMissResponse(run_id=run_id, near_misses=items)


@router.get("/signals", response_model=SignalsResponse)
def list_signals(
    db: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=500),
    since_date: date | None = Query(None),
    until_date: date | None = Query(None),
    leader: str | None = Query(None),
    follower: str | None = Query(None),
    group: str | None = Query(None),
) -> SignalsResponse:
    """List follower opportunity signals with optional filters."""
    repo = LeaderFollowerSignalRepository(db)
    signals = repo.list_signals(
        limit=limit,
        since_date=since_date,
        until_date=until_date,
        leader=leader,
        follower=follower,
        group=group,
    )
    items = [_signal_to_item(s) for s in signals]
    diagnostics = _build_signals_diagnostics(db) if not items else None
    return SignalsResponse(signals=items, diagnostics=diagnostics)


# --- Evaluation endpoints (007) ---


class EvalHorizonMetrics(BaseModel):
    """Per-horizon metrics for summary."""

    win_rate: float
    avg_return_pct: float
    median_return_pct: float
    evaluable_count: int


class EvalEventHorizonMetrics(BaseModel):
    """Per-horizon event-level metrics (one event = one leader-date)."""

    event_win_rate: float
    event_avg_return_pct: float
    event_count: int


class EvalSummaryResponse(BaseModel):
    """Response for GET /evaluation/summary."""

    total_signals: int
    total_events: int
    signals_per_day: float
    events_per_day: float
    date_range: dict[str, str | None]
    by_horizon: dict[str, EvalHorizonMetrics]
    by_event: dict[str, EvalEventHorizonMetrics]
    duplicate_overlap: dict[str, int | float]


@router.get("/evaluation/summary", response_model=EvalSummaryResponse)
def get_evaluation_summary(
    db: Session = Depends(get_session),
    since_date: date | None = Query(None, description="Filter signals with signal_date >="),
    until_date: date | None = Query(None, description="Filter signals with signal_date <="),
    leader: str | None = Query(None),
    follower: str | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
) -> EvalSummaryResponse:
    """Aggregate evaluation metrics for leader-follower signals."""
    signals, price_by_symbol, horizons = run_evaluation(
        db, since_date=since_date, until_date=until_date, leader=leader, follower=follower, limit=limit
    )
    summary = aggregate_summary(signals, price_by_symbol, horizons)
    # Convert by_horizon to Pydantic models
    by_horizon: dict[str, EvalHorizonMetrics] = {}
    for k, v in summary["by_horizon"].items():
        by_horizon[k] = EvalHorizonMetrics(
            win_rate=v["win_rate"],
            avg_return_pct=v["avg_return_pct"],
            median_return_pct=v["median_return_pct"],
            evaluable_count=v["evaluable_count"],
        )
    by_event: dict[str, EvalEventHorizonMetrics] = {}
    for k, v in (summary.get("by_event") or {}).items():
        by_event[k] = EvalEventHorizonMetrics(
            event_win_rate=v["event_win_rate"],
            event_avg_return_pct=v["event_avg_return_pct"],
            event_count=v["event_count"],
        )
    return EvalSummaryResponse(
        total_signals=summary["total_signals"],
        total_events=summary.get("total_events", 0),
        signals_per_day=summary["signals_per_day"],
        events_per_day=summary.get("events_per_day", 0.0),
        date_range=summary["date_range"],
        by_horizon=by_horizon,
        by_event=by_event,
        duplicate_overlap=summary["duplicate_overlap"],
    )


class EvalPairHorizon(BaseModel):
    """Per-horizon metrics for a pair."""

    win_rate: float
    avg_return_pct: float


class EvalPairItem(BaseModel):
    """Single pair for GET /evaluation/pairs."""

    leader_symbol: str
    follower_symbol: str
    signal_count: int
    model_config = ConfigDict(extra="allow")  # Allow 1d, 3d, 5d keys


@router.get("/evaluation/pairs")
def get_evaluation_pairs(
    db: Session = Depends(get_session),
    since_date: date | None = Query(None),
    until_date: date | None = Query(None),
    leader: str | None = Query(None),
    follower: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    """Pair-level evaluation aggregates."""
    signals, price_by_symbol, horizons = run_evaluation(
        db, since_date=since_date, until_date=until_date, leader=leader, follower=follower, limit=limit
    )
    pairs = aggregate_by_pair(signals, price_by_symbol, horizons)
    return {"pairs": pairs}


class EvalSignalItem(BaseModel):
    """Single signal with outcomes for GET /evaluation/signals."""

    model_config = ConfigDict(extra="allow")


@router.get("/evaluation/signals")
def get_evaluation_signals(
    db: Session = Depends(get_session),
    since_date: date | None = Query(None),
    until_date: date | None = Query(None),
    leader: str | None = Query(None),
    follower: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    """Signal-level evaluation outcomes."""
    signals, price_by_symbol, horizons = run_evaluation(
        db, since_date=since_date, until_date=until_date, leader=leader, follower=follower, limit=limit
    )
    items = [evaluate_signal(s, price_by_symbol, horizons) for s in signals]
    return {"signals": items}


@router.get("/evaluation/top-pairs")
def get_evaluation_top_pairs(
    db: Session = Depends(get_session),
    since_date: date | None = Query(None),
    until_date: date | None = Query(None),
    leader: str | None = Query(None),
    follower: str | None = Query(None),
    n: int = Query(10, ge=1, le=50),
    metric: str = Query("avg_return_pct", description="Metric to rank by"),
    horizon: str = Query("1d", description="Horizon key e.g. 1d, 3d, 5d"),
    min_sample: int = Query(2, ge=1, le=10),
    limit: int = Query(500, ge=1, le=2000),
) -> dict[str, Any]:
    """Top N pairs by chosen metric."""
    signals, price_by_symbol, horizons = run_evaluation(
        db, since_date=since_date, until_date=until_date, leader=leader, follower=follower, limit=limit
    )
    pairs = aggregate_by_pair(signals, price_by_symbol, horizons)
    filtered = [p for p in pairs if p["signal_count"] >= min_sample]
    sorted_pairs = sorted(
        filtered,
        key=lambda p: p.get(horizon, {}).get(metric, float("-inf")),
        reverse=True,
    )
    return {"pairs": sorted_pairs[:n]}


@router.get("/evaluation/bottom-pairs")
def get_evaluation_bottom_pairs(
    db: Session = Depends(get_session),
    since_date: date | None = Query(None),
    until_date: date | None = Query(None),
    leader: str | None = Query(None),
    follower: str | None = Query(None),
    n: int = Query(10, ge=1, le=50),
    metric: str = Query("avg_return_pct", description="Metric to rank by"),
    horizon: str = Query("1d", description="Horizon key e.g. 1d, 3d, 5d"),
    min_sample: int = Query(2, ge=1, le=10),
    limit: int = Query(500, ge=1, le=2000),
) -> dict[str, Any]:
    """Bottom N pairs by chosen metric."""
    signals, price_by_symbol, horizons = run_evaluation(
        db, since_date=since_date, until_date=until_date, leader=leader, follower=follower, limit=limit
    )
    pairs = aggregate_by_pair(signals, price_by_symbol, horizons)
    filtered = [p for p in pairs if p["signal_count"] >= min_sample]
    sorted_pairs = sorted(
        filtered,
        key=lambda p: p.get(horizon, {}).get(metric, float("inf")),
        reverse=False,
    )
    return {"pairs": sorted_pairs[:n]}


# --- Pairs filtering and ranking (009) ---

SORT_BY_CHOICES = frozenset({"avg_return_1d", "win_rate_1d", "signal_count", "avg_return_3d", "avg_return_5d"})


@router.get("/pairs/ranked")
def get_pairs_ranked(
    db: Session = Depends(get_session),
    since_date: date | None = Query(None),
    until_date: date | None = Query(None),
    leader: str | None = Query(None),
    follower: str | None = Query(None),
    sort_by: str = Query("avg_return_1d", description="Field to sort by"),
    sort_order: str = Query("desc", description="asc or desc"),
    limit: int = Query(500, ge=1, le=2000),
) -> dict[str, Any]:
    """Ranked pairs from evaluation. Optional filtering via config thresholds."""
    if sort_by not in SORT_BY_CHOICES:
        raise HTTPException(status_code=400, detail=f"sort_by must be one of {sorted(SORT_BY_CHOICES)}")
    sort_order_val = sort_order.lower()
    if sort_order_val not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="sort_order must be asc or desc")

    signals, price_by_symbol, horizons = run_evaluation(
        db, since_date=since_date, until_date=until_date, leader=leader, follower=follower, limit=limit
    )
    pairs = aggregate_by_pair(signals, price_by_symbol, horizons)
    cfg = get_settings()
    apply_filter = cfg.enable_pair_filtering_for_signals
    min_sc = cfg.leader_follower_pair_min_signal_count
    min_avg = cfg.leader_follower_pair_min_avg_return_1d
    min_wr = cfg.leader_follower_pair_min_win_rate_1d
    if apply_filter:
        passing, _ = filter_pairs_by_thresholds(pairs, min_sc, min_avg, min_wr)
        pairs = passing
    ranked = rank_pairs(pairs, sort_by=sort_by, sort_order=sort_order_val)
    return {"pairs": ranked}


@router.get("/pairs/filtered")
def get_pairs_filtered(
    db: Session = Depends(get_session),
    since_date: date | None = Query(None),
    until_date: date | None = Query(None),
    leader: str | None = Query(None),
    follower: str | None = Query(None),
    min_signal_count: int | None = Query(None),
    min_avg_return_1d: float | None = Query(None),
    min_win_rate_1d: float | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
) -> dict[str, Any]:
    """Pairs with filter_status. Override thresholds via query params."""
    cfg = get_settings()
    min_sc = min_signal_count if min_signal_count is not None else cfg.leader_follower_pair_min_signal_count
    min_avg = min_avg_return_1d if min_avg_return_1d is not None else cfg.leader_follower_pair_min_avg_return_1d
    min_wr = min_win_rate_1d if min_win_rate_1d is not None else cfg.leader_follower_pair_min_win_rate_1d

    signals, price_by_symbol, horizons = run_evaluation(
        db, since_date=since_date, until_date=until_date, leader=leader, follower=follower, limit=limit
    )
    pairs = aggregate_by_pair(signals, price_by_symbol, horizons)
    passing, all_with_status = filter_pairs_by_thresholds(pairs, min_sc, min_avg, min_wr)
    return {
        "pairs": all_with_status,
        "total_before_filter": len(pairs),
        "total_after_filter": len(passing),
    }


@router.get("/pairs/blacklist")
def get_pairs_blacklist() -> dict[str, Any]:
    """Blacklist of pairs (MVP: always empty)."""
    return {"pairs": []}
