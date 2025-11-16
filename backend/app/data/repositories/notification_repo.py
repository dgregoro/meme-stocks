from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.notification import Notification
from backend.app.utils.errors import DataAccessError


class NotificationRepository:
    """Repository for Notification entities."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, notification: Notification) -> None:
        try:
            self._session.add(notification)
            self._session.flush()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to add notification") from exc

    def list_unread(self, limit: int = 100) -> Sequence[Notification]:
        stmt = (
            select(Notification)
            .where(Notification.read.is_(False))
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list notifications") from exc
