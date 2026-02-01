from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.job_execution import JobExecution
from backend.app.utils.errors import DataAccessError


class JobExecutionRepository:
    """Repository for tracking job execution history."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_last_run(self, job_name: str) -> datetime | None:
        """Get the last run time for a job, or None if never run."""
        stmt = select(JobExecution).where(JobExecution.job_name == job_name)
        try:
            job = self._session.execute(stmt).scalar_one_or_none()
            return job.last_run_at if job else None
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError(f"Failed to get last run for job {job_name}") from exc

    def record_run(self, job_name: str, run_at: datetime | None = None) -> None:
        """Record that a job ran at the given time (or now if not provided)."""
        if run_at is None:
            run_at = datetime.now(timezone.utc)

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
            self._session.flush()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError(f"Failed to record run for job {job_name}") from exc
