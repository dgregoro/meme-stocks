"""Repository for global job locks (TTL lease, SQLite-safe)."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import cast

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from backend.app.models.job_lock import JobLock
from backend.app.utils.errors import DataAccessError


class JobLockRepository:
    """Atomic acquire/release/heartbeat for job_locks. Works on SQLite and Postgres."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def try_acquire_lock(
        self,
        name: str,
        owner: str,
        ttl_seconds: int,
        now: datetime | None = None,
    ) -> bool:
        """Acquire the lock if not held or expired. Single transaction, atomic.

        Semantics: INSERT if row missing; if row exists (unique constraint), only acquire
        when expires_at <= now by updating the row.
        Returns True if we acquired, False if another owner holds and has not expired.
        """
        if now is None:
            now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=ttl_seconds)
        try:
            self._session.add(
                JobLock(
                    name=name,
                    owner=owner,
                    acquired_at=now,
                    expires_at=expires,
                    heartbeat_at=now,
                )
            )
            self._session.flush()
            return True
        except IntegrityError:
            self._session.rollback()
            # Row exists: try to take over only if expired
            stmt = select(JobLock).where(JobLock.name == name)
            row = self._session.execute(stmt).scalar_one_or_none()
            if row is None:
                self._session.add(
                    JobLock(
                        name=name,
                        owner=owner,
                        acquired_at=now,
                        expires_at=expires,
                        heartbeat_at=now,
                    )
                )
                self._session.flush()
                return True
            # SQLite returns naive datetimes; normalize for comparison
            exp = row.expires_at
            if exp is not None and exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp is not None and exp <= now:
                row.owner = owner
                row.acquired_at = now
                row.heartbeat_at = now
                row.expires_at = expires
                self._session.flush()
                return True
            return False
        except SQLAlchemyError as exc:
            raise DataAccessError("Failed to acquire job lock") from exc

    def heartbeat(
        self,
        name: str,
        owner: str,
        ttl_seconds: int,
        now: datetime | None = None,
    ) -> bool:
        """Extend expires_at and heartbeat_at only if owner matches. Caller may commit."""
        if now is None:
            now = datetime.now(timezone.utc)
        new_expires = now + timedelta(seconds=ttl_seconds)
        stmt = (
            update(JobLock)
            .where(JobLock.name == name, JobLock.owner == owner)
            .values(heartbeat_at=now, expires_at=new_expires)
        )
        try:
            result = cast(CursorResult[object], self._session.execute(stmt))
            return result.rowcount == 1
        except SQLAlchemyError as exc:
            raise DataAccessError("Failed to heartbeat job lock") from exc

    def clear_lock_by_name(self, name: str) -> int:
        """Remove lock row by name (ignores owner). For startup recovery after restart."""
        stmt = delete(JobLock).where(JobLock.name == name)
        try:
            result = cast(CursorResult[object], self._session.execute(stmt))
            return result.rowcount or 0
        except SQLAlchemyError as exc:
            raise DataAccessError(f"Failed to clear lock {name}") from exc

    def release_lock(self, name: str, owner: str) -> bool:
        """Release the lock only if owner matches (delete row)."""
        stmt = delete(JobLock).where(JobLock.name == name, JobLock.owner == owner)
        try:
            result = cast(CursorResult[object], self._session.execute(stmt))
            return result.rowcount == 1
        except SQLAlchemyError as exc:
            raise DataAccessError("Failed to release job lock") from exc

    def get_lock(self, name: str) -> JobLock | None:
        """Return the current lock row for name, or None."""
        stmt = select(JobLock).where(JobLock.name == name)
        try:
            return self._session.execute(stmt).scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise DataAccessError("Failed to get job lock") from exc
