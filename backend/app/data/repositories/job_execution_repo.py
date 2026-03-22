from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.job_execution import JobExecution
from backend.app.models.job_run_history import JobRunHistory
from backend.app.utils.errors import DataAccessError


SUMMARY_MAX_LENGTH = 240


def _truncate_summary(text: str | None) -> str | None:
    """Truncate summary to SUMMARY_MAX_LENGTH chars."""
    if not text:
        return None
    if len(text) <= SUMMARY_MAX_LENGTH:
        return text
    return text[: SUMMARY_MAX_LENGTH - 1] + "…"


def _as_utc_aware(dt: datetime | None) -> datetime | None:
    """Normalize datetime to UTC-aware; treat naive as UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class JobExecutionRepository:
    """Repository for tracking job execution history."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_last_run(self, job_name: str) -> datetime | None:
        """Get the last run time for a job, or None if never run."""
        stmt = select(JobExecution).where(JobExecution.job_name == job_name)
        try:
            job = self._session.execute(stmt).scalar_one_or_none()
            return _as_utc_aware(job.last_run_at) if job else None
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError(f"Failed to get last run for job {job_name}") from exc

    def get_last_success(self, job_name: str) -> datetime | None:
        """Get the last successful run time for a job, or None if no successful run."""
        stmt = (
            select(JobRunHistory.run_at)
            .where(JobRunHistory.job_name == job_name, JobRunHistory.success.is_(True))
            .order_by(JobRunHistory.run_at.desc())
            .limit(1)
        )
        try:
            run_at_val = self._session.execute(stmt).scalar_one_or_none()
            return _as_utc_aware(run_at_val) if run_at_val is not None else None
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError(f"Failed to get last success for job {job_name}") from exc

    def get_last_run_summary(self, job_name: str) -> str | None:
        """Get the summary from the most recent run (success or failure), or None."""
        stmt = (
            select(JobRunHistory.summary)
            .where(JobRunHistory.job_name == job_name)
            .order_by(JobRunHistory.run_at.desc())
            .limit(1)
        )
        try:
            return self._session.execute(stmt).scalar_one_or_none()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError(f"Failed to get last run summary for job {job_name}") from exc

    def get_last_success_summary(self, job_name: str) -> str | None:
        """Get the summary from the most recent successful run, or None."""
        stmt = (
            select(JobRunHistory.summary)
            .where(JobRunHistory.job_name == job_name, JobRunHistory.success.is_(True))
            .order_by(JobRunHistory.run_at.desc())
            .limit(1)
        )
        try:
            return self._session.execute(stmt).scalar_one_or_none()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError(f"Failed to get last success summary for job {job_name}") from exc

    def record_run(
        self,
        job_name: str,
        run_at: datetime | None = None,
        *,
        success: bool = True,
        error_message: str | None = None,
        started_at: datetime | None = None,
        duration_seconds: float | None = None,
        summary: str | None = None,
        metrics: Mapping[str, Any] | None = None,
    ) -> JobRunHistory:
        """Record that a job ran at the given time (or now if not provided). Exactly one row per call.
        Returns the created JobRunHistory row for tests and callers.
        """
        if run_at is None:
            run_at = datetime.now(timezone.utc)
        run_at = _as_utc_aware(run_at) or run_at
        started_at_norm = _as_utc_aware(started_at) if started_at is not None else None

        metrics_str: str | None = None
        if metrics is not None and len(metrics) > 0:
            metrics_str = json.dumps(dict(metrics), separators=(",", ":"), sort_keys=True)

        summary_truncated = _truncate_summary(summary)

        stmt = select(JobExecution).where(JobExecution.job_name == job_name)
        try:
            existing = self._session.execute(stmt).scalar_one_or_none()
            if existing:
                existing.last_run_at = run_at
                existing.updated_at = datetime.now(timezone.utc)
            else:
                job = JobExecution(
                    job_name=job_name,
                    last_run_at=run_at,
                )
                self._session.add(job)
            history = JobRunHistory(
                job_name=job_name,
                run_at=run_at,
                started_at=started_at_norm,
                duration_seconds=duration_seconds,
                success=success,
                error_message=(error_message[:500] if error_message else None),
                summary=summary_truncated,
                metrics_json=metrics_str,
            )
            self._session.add(history)
            self._session.flush()
            return history
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError(f"Failed to record run for job {job_name}") from exc

    def insert_run_start(self, job_name: str, started_at: datetime | None = None) -> int:
        """Insert a run row at job start; return its id. Call complete_run to finish."""
        import time

        from sqlalchemy.exc import OperationalError

        if started_at is None:
            started_at = datetime.now(timezone.utc)
        started_at = _as_utc_aware(started_at) or started_at
        stmt = select(JobExecution).where(JobExecution.job_name == job_name)
        last_exc: SQLAlchemyError | None = None
        for attempt in range(4):  # 4 attempts: 0s, 1s, 2s, 3s delays
            try:
                existing = self._session.execute(stmt).scalar_one_or_none()
                if existing:
                    existing.last_run_at = started_at
                    existing.updated_at = datetime.now(timezone.utc)
                else:
                    self._session.add(JobExecution(job_name=job_name, last_run_at=started_at))
                history = JobRunHistory(
                    job_name=job_name,
                    run_at=started_at,
                    started_at=started_at,
                    success=False,
                    error_message=None,
                    summary=None,
                    metrics_json=None,
                )
                self._session.add(history)
                self._session.flush()
                return history.id
            except OperationalError as exc:
                msg = str(getattr(exc, "orig", exc)).lower()
                if "locked" in msg and attempt < 3:
                    last_exc = exc
                    self._session.rollback()
                    time.sleep(1 + attempt)
                    continue
                raise DataAccessError(f"Failed to insert run start for {job_name}") from exc
            except SQLAlchemyError as exc:  # pragma: no cover
                raise DataAccessError(f"Failed to insert run start for {job_name}") from exc
        if last_exc:
            raise DataAccessError(f"Failed to insert run start for {job_name}") from last_exc
        raise DataAccessError(f"Failed to insert run start for {job_name}")

    def complete_run(
        self,
        run_id: int,
        *,
        success: bool = True,
        run_at: datetime | None = None,
        error_message: str | None = None,
        duration_seconds: float | None = None,
        summary: str | None = None,
        metrics: Mapping[str, Any] | None = None,
    ) -> None:
        """Update a run row created by insert_run_start with final data."""
        stmt = select(JobRunHistory).where(JobRunHistory.id == run_id)
        try:
            row = self._session.execute(stmt).scalar_one_or_none()
            if row is None:
                raise DataAccessError(f"Run id {run_id} not found")
            if run_at is not None:
                row.run_at = _as_utc_aware(run_at) or run_at
            row.success = success
            row.error_message = error_message[:500] if error_message else None
            row.duration_seconds = duration_seconds
            row.summary = _truncate_summary(summary)
            if metrics is not None and len(metrics) > 0:
                row.metrics_json = json.dumps(dict(metrics), separators=(",", ":"), sort_keys=True)
            self._session.flush()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError(f"Failed to complete run {run_id}") from exc

    def list_recent_runs(
        self,
        job_name: str | None = None,
        limit: int = 200,
    ) -> Sequence[JobRunHistory]:
        """Return the last `limit` runs, most recent first. If job_name set, filter by job."""
        stmt = select(JobRunHistory).order_by(JobRunHistory.run_at.desc()).limit(limit)
        if job_name is not None:
            stmt = stmt.where(JobRunHistory.job_name == job_name)
        try:
            result = self._session.execute(stmt)
            return result.scalars().all()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list job runs") from exc
