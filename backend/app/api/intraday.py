"""Intraday minute-bar status and control API."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from backend.app.utils.datetime_utils import ensure_utc_aware

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.data.database import get_session
from backend.app.data.repositories.intraday_ingest_repo import IntradayIngestRepository
from backend.app.services.intraday_ingestion_service import run_intraday_ingestion
from backend.app.utils.api_errors import error_detail
from backend.app.utils.errors import IngestionAlreadyRunningError

router = APIRouter(prefix="/api/intraday", tags=["intraday"])


class IntradayStatusResponse(BaseModel):
    """Status of intraday ingestion and Alpaca free-plan settings."""

    alpaca_feed: str
    free_plan_mode: bool
    sip_delay_minutes: int
    end_time_safety_minutes: int
    effective_data_lag_minutes: int
    notes: str
    # Ingestion progress
    counts_by_status: dict[str, int]
    newest_last_ts: str | None
    oldest_last_ts: str | None
    latest_run: dict | None
    intraday_ingestion_enabled: bool
    lock: dict  # Governance: enabled, held, owner?, expires_at?, heartbeat_at?


@router.get("/status", response_model=IntradayStatusResponse)
def get_intraday_status(db: Session = Depends(get_session)) -> IntradayStatusResponse:
    """Return Alpaca feed, safety window, and ingestion progress (counts, last_ts range, latest run)."""
    settings = get_settings()
    safety = settings.alpaca_end_time_safety_minutes
    sip_delay = settings.alpaca_sip_delay_minutes
    effective_lag = max(safety, sip_delay)
    notes = (
        f"Historical bars feed={settings.alpaca_bars_feed}. "
        f"Free plan mode: ingestion ends at now - {safety} minutes "
        f"(SIP delay is {sip_delay}m; effective lag is {effective_lag}m)."
        if settings.alpaca_free_plan_mode
        else f"Historical bars feed={settings.alpaca_bars_feed}. Free plan mode disabled; end time = now."
    )

    repo = IntradayIngestRepository(db)
    counts = repo.count_by_status()
    newest = repo.get_newest_last_ts()
    oldest = repo.get_oldest_last_ts()
    latest = repo.get_latest_run()
    latest_run_dict: dict | None = None
    if latest:
        latest_run_dict = {
            "id": latest.id,
            "started_at": latest.started_at.isoformat() if latest.started_at else None,
            "ended_at": latest.ended_at.isoformat() if latest.ended_at else None,
            "symbols_count": latest.symbols_count,
            "bars_written": latest.bars_written,
            "errors_count": latest.errors_count,
            "notes": latest.notes,
        }

    lock_enabled = getattr(settings, "intraday_lock_enabled", True)
    lock_name = getattr(settings, "intraday_lock_name", "intraday_ingestion")
    lock_info: dict = {"enabled": lock_enabled, "held": False}
    if lock_enabled:
        from backend.app.data.repositories.job_lock_repo import JobLockRepository

        lock_repo = JobLockRepository(db)
        current_lock = lock_repo.get_lock(lock_name)
        now = datetime.now(timezone.utc)
        expires_at = ensure_utc_aware(current_lock.expires_at) if current_lock else None
        if current_lock and expires_at and expires_at > now:
            lock_info["held"] = True
            lock_info["owner"] = current_lock.owner
            lock_info["expires_at"] = expires_at.isoformat()
            lock_info["heartbeat_at"] = current_lock.heartbeat_at.isoformat() if current_lock.heartbeat_at else None
        elif current_lock:
            lock_info["owner"] = current_lock.owner
            lock_info["expires_at"] = current_lock.expires_at.isoformat() if current_lock.expires_at else None

    return IntradayStatusResponse(
        alpaca_feed=settings.alpaca_bars_feed,
        free_plan_mode=settings.alpaca_free_plan_mode,
        sip_delay_minutes=sip_delay,
        end_time_safety_minutes=safety,
        effective_data_lag_minutes=effective_lag,
        notes=notes,
        counts_by_status=counts,
        newest_last_ts=newest.isoformat() if newest else None,
        oldest_last_ts=oldest.isoformat() if oldest else None,
        latest_run=latest_run_dict,
        intraday_ingestion_enabled=getattr(settings, "intraday_ingestion_enabled", False),
        lock=lock_info,
    )


class RunOnceResponse(BaseModel):
    """Result of a single intraday ingestion run."""

    symbols_processed: int
    bars_written: int
    errors_count: int
    start_utc: str | None
    end_utc: str | None
    safe_end_used: str | None
    feed: str
    free_plan_mode: bool


@router.post("/run-once", response_model=RunOnceResponse)
def post_intraday_run_once(db: Session = Depends(get_session)) -> RunOnceResponse:
    """Trigger one intraday ingestion run (tracked universe). Returns 409 if already running."""
    owner = f"api:{uuid4()}"
    try:
        summary = run_intraday_ingestion(db, universe=None, owner=owner)
    except IngestionAlreadyRunningError as e:
        detail = error_detail(
            "ConflictError",
            e.args[0] if e.args else "Intraday ingestion already in progress",
            details={"owner": e.owner, "expires_at": e.expires_at} if (e.owner or e.expires_at) else None,
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from e
    db.commit()
    return RunOnceResponse(
        symbols_processed=summary["symbols_processed"],
        bars_written=summary["bars_written"],
        errors_count=summary["errors_count"],
        start_utc=summary.get("start_utc"),
        end_utc=summary.get("end_utc"),
        safe_end_used=summary.get("safe_end_used"),
        feed=summary["feed"],
        free_plan_mode=summary["free_plan_mode"],
    )


@router.post("/pause")
def post_intraday_pause(
    symbol: str = Query(..., description="Symbol to pause ingestion for"),
    db: Session = Depends(get_session),
) -> dict:
    """Pause ingestion for a symbol."""
    repo = IntradayIngestRepository(db)
    repo.ensure_symbols([symbol])
    db.commit()
    repo.pause(symbol)
    db.commit()
    return {"symbol": symbol, "status": "paused"}


@router.post("/resume")
def post_intraday_resume(
    symbol: str = Query(..., description="Symbol to resume ingestion for"),
    db: Session = Depends(get_session),
) -> dict:
    """Resume ingestion for a symbol."""
    repo = IntradayIngestRepository(db)
    existing = repo.get_states([symbol])
    if symbol not in existing:
        return {
            "symbol": symbol,
            "status": "active",
            "message": "symbol not in state; will be picked up when universe is ingested",
        }
    repo.resume(symbol)
    db.commit()
    return {"symbol": symbol, "status": "active"}
