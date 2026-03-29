"""Read-only API for volume spike research events and evaluation (015)."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.data.database import get_session
from backend.app.data.repositories.volume_spike_event_repo import VolumeSpikeEventRepository
from backend.app.services.volume_spike_evaluation_service import (
    aggregate_by_symbol,
    aggregate_by_type_flat,
    aggregate_volume_spike_summary,
    run_volume_spike_evaluation,
)
from backend.app.utils.api_errors import raise_api_error

router = APIRouter(prefix="/api/volume-spike", tags=["volume-spike"])


def _parse_opt_date(name: str, s: str | None) -> date | None:
    if s is None or s == "":
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise_api_error(400, "VALIDATION_ERROR", f"Invalid {name}; use YYYY-MM-DD", {"field": name})


class VolumeSpikeEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    event_date: date
    volume: int
    baseline_volume: float
    volume_ratio: float
    same_day_return_pct: float
    event_type: str
    created_at: str


class EventsListResponse(BaseModel):
    events: list[VolumeSpikeEventOut]
    total: int


def _event_to_out(e: Any) -> VolumeSpikeEventOut:
    ca = e.created_at
    created = ca.isoformat() if hasattr(ca, "isoformat") else str(ca)
    return VolumeSpikeEventOut(
        id=e.id,
        symbol=e.symbol,
        event_date=e.event_date,
        volume=e.volume,
        baseline_volume=e.baseline_volume,
        volume_ratio=e.volume_ratio,
        same_day_return_pct=e.same_day_return_pct,
        event_type=e.event_type,
        created_at=created,
    )


@router.get("/events", response_model=EventsListResponse)
def list_events(
    db: Session = Depends(get_session),
    symbol: str | None = Query(None),
    since_date: str | None = Query(None),
    until_date: str | None = Query(None),
    event_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
) -> EventsListResponse:
    sd = _parse_opt_date("since_date", since_date)
    ud = _parse_opt_date("until_date", until_date)
    if event_type and event_type not in ("spike_up", "spike_down", "spike_flat"):
        raise_api_error(
            400,
            "VALIDATION_ERROR",
            "event_type must be spike_up, spike_down, or spike_flat",
            {"field": "event_type"},
        )
    repo = VolumeSpikeEventRepository(db)
    total = repo.count_filtered(symbol=symbol, since_date=sd, until_date=ud, event_type=event_type)
    rows = repo.list_filtered(
        symbol=symbol,
        since_date=sd,
        until_date=ud,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )
    return EventsListResponse(events=[_event_to_out(r) for r in rows], total=total)


@router.get("/evaluation/summary")
def evaluation_summary(
    db: Session = Depends(get_session),
    since_date: str | None = Query(None),
    until_date: str | None = Query(None),
    symbol: str | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
) -> dict[str, Any]:
    sd = _parse_opt_date("since_date", since_date)
    ud = _parse_opt_date("until_date", until_date)
    events, price_by_symbol, horizons = run_volume_spike_evaluation(
        db, since_date=sd, until_date=ud, symbol=symbol, limit=limit
    )
    summary = aggregate_volume_spike_summary(events, price_by_symbol, horizons)
    return summary


@router.get("/evaluation/by-symbol")
def evaluation_by_symbol(
    db: Session = Depends(get_session),
    since_date: str | None = Query(None),
    until_date: str | None = Query(None),
    symbol: str | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    min_sample: int = Query(1, ge=1, le=1000),
) -> dict[str, Any]:
    sd = _parse_opt_date("since_date", since_date)
    ud = _parse_opt_date("until_date", until_date)
    events, price_by_symbol, horizons = run_volume_spike_evaluation(
        db, since_date=sd, until_date=ud, symbol=symbol, limit=limit
    )
    rows = aggregate_by_symbol(events, price_by_symbol, horizons, min_sample=min_sample)
    return {"symbols": rows, "min_sample": min_sample}


@router.get("/evaluation/by-type")
def evaluation_by_type(
    db: Session = Depends(get_session),
    since_date: str | None = Query(None),
    until_date: str | None = Query(None),
    symbol: str | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
) -> dict[str, Any]:
    sd = _parse_opt_date("since_date", since_date)
    ud = _parse_opt_date("until_date", until_date)
    events, price_by_symbol, horizons = run_volume_spike_evaluation(
        db, since_date=sd, until_date=ud, symbol=symbol, limit=limit
    )
    by_type = aggregate_by_type_flat(events, price_by_symbol, horizons)
    return {"by_event_type": by_type, "forward_anchor": "event_date_close", "horizons_trading_days": list(horizons)}
