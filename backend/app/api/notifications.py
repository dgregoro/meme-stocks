from __future__ import annotations

from typing import Any, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.data.database import get_session
from backend.app.data.repositories.notification_repo import NotificationRepository
from backend.app.services.combined_signal_service import parse_signal_metadata


router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationResponse(BaseModel):
    id: int
    stock_symbol: str
    type: str
    message: str
    severity: str
    created_at: str
    read: bool
    signal_metadata: dict[str, Any] | None = None


@router.get("", response_model=List[NotificationResponse])
def list_notifications(
    db: Session = Depends(get_session),
) -> List[NotificationResponse]:
    """List unread notifications (volume spikes, price moves, sentiment shifts, combined signals)."""
    repo = NotificationRepository(db)
    notifications = repo.list_unread()
    return [
        NotificationResponse(
            id=n.id,
            stock_symbol=n.stock_symbol,
            type=n.type,
            message=n.message,
            severity=n.severity,
            created_at=n.created_at.isoformat(),
            read=n.read,
            signal_metadata=parse_signal_metadata(n.signal_metadata),
        )
        for n in notifications
    ]
