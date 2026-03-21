"""Leader-follower signals API."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.data.database import get_session
from backend.app.data.repositories.leader_follower_signal_repo import LeaderFollowerSignalRepository

router = APIRouter(prefix="/api/leader-follower", tags=["leader-follower"])


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


class SignalsResponse(BaseModel):
    """Response for GET /signals."""

    signals: list[SignalItem]


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
    return SignalsResponse(signals=items)
