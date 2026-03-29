"""Read-only API for extreme move research (016)."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.data.database import get_session
from backend.app.data.repositories.extreme_move_event_repo import ExtremeMoveEventRepository
from backend.app.services.extreme_move_evaluation_service import (
    aggregate_by_symbol,
    aggregate_by_type_flat,
    aggregate_evaluation_by_magnitude,
    aggregate_evaluation_by_magnitude_volume,
    aggregate_evaluation_by_volume,
    aggregate_extreme_move_summary,
    run_extreme_move_evaluation,
)
from backend.app.utils.api_errors import raise_api_error

router = APIRouter(prefix="/api/extreme-move", tags=["extreme-move"])


def _parse_opt_date(name: str, s: str | None) -> date | None:
    if s is None or s == "":
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise_api_error(400, "VALIDATION_ERROR", f"Invalid {name}; use YYYY-MM-DD", {"field": name})


class ExtremeMoveEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    event_date: date
    return_pct: float
    event_type: str
    magnitude_bucket: str | None = None
    volume_ratio: float | None = None
    volume_bucket: str | None = None
    created_at: str


class EventsListResponse(BaseModel):
    events: list[ExtremeMoveEventOut]
    total: int


def _event_to_out(e: Any) -> ExtremeMoveEventOut:
    ca = e.created_at
    created = ca.isoformat() if hasattr(ca, "isoformat") else str(ca)
    return ExtremeMoveEventOut(
        id=e.id,
        symbol=e.symbol,
        event_date=e.event_date,
        return_pct=e.return_pct,
        event_type=e.event_type,
        magnitude_bucket=getattr(e, "magnitude_bucket", None),
        volume_ratio=getattr(e, "volume_ratio", None),
        volume_bucket=getattr(e, "volume_bucket", None),
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
    if event_type and event_type not in ("extreme_up", "extreme_down"):
        raise_api_error(
            400,
            "VALIDATION_ERROR",
            "event_type must be extreme_up or extreme_down",
            {"field": "event_type"},
        )
    repo = ExtremeMoveEventRepository(db)
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
    events, price_by_symbol, horizons = run_extreme_move_evaluation(
        db, since_date=sd, until_date=ud, symbol=symbol, limit=limit
    )
    return aggregate_extreme_move_summary(events, price_by_symbol, horizons)


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
    events, price_by_symbol, horizons = run_extreme_move_evaluation(
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
    events, price_by_symbol, horizons = run_extreme_move_evaluation(
        db, since_date=sd, until_date=ud, symbol=symbol, limit=limit
    )
    by_type = aggregate_by_type_flat(events, price_by_symbol, horizons)
    return {"by_event_type": by_type, "forward_anchor": "event_date_close", "horizons_trading_days": list(horizons)}


@router.get("/evaluation/by-magnitude")
def evaluation_by_magnitude(
    db: Session = Depends(get_session),
    since_date: str | None = Query(None),
    until_date: str | None = Query(None),
    symbol: str | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
) -> dict[str, Any]:
    sd = _parse_opt_date("since_date", since_date)
    ud = _parse_opt_date("until_date", until_date)
    events, price_by_symbol, horizons = run_extreme_move_evaluation(
        db, since_date=sd, until_date=ud, symbol=symbol, limit=limit
    )
    by_mag = aggregate_evaluation_by_magnitude(events, price_by_symbol, horizons)
    return {
        "by_magnitude": by_mag,
        "forward_anchor": "event_date_close",
        "horizons_trading_days": list(horizons),
    }


@router.get("/evaluation/by-volume")
def evaluation_by_volume(
    db: Session = Depends(get_session),
    since_date: str | None = Query(None),
    until_date: str | None = Query(None),
    symbol: str | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
) -> dict[str, Any]:
    sd = _parse_opt_date("since_date", since_date)
    ud = _parse_opt_date("until_date", until_date)
    events, price_by_symbol, horizons = run_extreme_move_evaluation(
        db, since_date=sd, until_date=ud, symbol=symbol, limit=limit
    )
    by_vol = aggregate_evaluation_by_volume(events, price_by_symbol, horizons)
    return {
        "by_volume": by_vol,
        "forward_anchor": "event_date_close",
        "horizons_trading_days": list(horizons),
    }


@router.get("/evaluation/by-magnitude-volume")
def evaluation_by_magnitude_volume(
    db: Session = Depends(get_session),
    since_date: str | None = Query(None),
    until_date: str | None = Query(None),
    symbol: str | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
) -> dict[str, Any]:
    sd = _parse_opt_date("since_date", since_date)
    ud = _parse_opt_date("until_date", until_date)
    events, price_by_symbol, horizons = run_extreme_move_evaluation(
        db, since_date=sd, until_date=ud, symbol=symbol, limit=limit
    )
    combined = aggregate_evaluation_by_magnitude_volume(events, price_by_symbol, horizons)
    return {
        "by_magnitude_volume": combined,
        "forward_anchor": "event_date_close",
        "horizons_trading_days": list(horizons),
    }
