"""Leader-follower signals API."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.data.database import get_session
from backend.app.data.repositories.job_execution_repo import JobExecutionRepository
from backend.app.data.repositories.leader_event_repo import LeaderEventRepository
from backend.app.data.repositories.leader_follower_candidate_repo import LeaderFollowerCandidateRepository
from backend.app.data.repositories.leader_follower_signal_repo import LeaderFollowerSignalRepository

router = APIRouter(prefix="/api/leader-follower", tags=["leader-follower"])

LEADER_FOLLOWER_JOB = "leader_follower_detection"

EmptyReason = Literal["no_run", "failed", "no_leaders", "no_candidates", "no_confirmations", "ok"]


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
    leaders = metrics.get("leader_events_detected", 0) or 0
    candidates = metrics.get("follower_candidates_found", 0) or 0
    signals = metrics.get("signals_emitted", 0) or 0
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
    runs = job_repo.list_recent_runs(job_name=LEADER_FOLLOWER_JOB, limit=1)
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
) -> RunsResponse:
    """Recent job runs with full metrics for leader-follower detection."""
    job_repo = JobExecutionRepository(db)
    runs = job_repo.list_recent_runs(job_name=LEADER_FOLLOWER_JOB, limit=limit)
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
    runs = job_repo.list_recent_runs(job_name=LEADER_FOLLOWER_JOB, limit=1)
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


@router.get("/signals", response_model=SignalsResponse)
def list_signals(
    db: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=500),
    since_date: date | None = Query(None),
    leader: str | None = Query(None),
    group: str | None = Query(None),
) -> SignalsResponse:
    """List follower opportunity signals with optional filters."""
    repo = LeaderFollowerSignalRepository(db)
    signals = repo.list_signals(
        limit=limit,
        since_date=since_date,
        leader=leader,
        group=group,
    )
    items = [_signal_to_item(s) for s in signals]
    diagnostics = _build_signals_diagnostics(db) if not items else None
    return SignalsResponse(signals=items, diagnostics=diagnostics)
