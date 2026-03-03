"""Tests for JobExecutionRepository: last_run, last_success, list_recent_runs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Generator

import pytest
from sqlalchemy.orm import Session

from backend.app.data.database import Base, SessionLocal, engine
from backend.app.data.repositories.job_execution_repo import JobExecutionRepository
from backend.app.models.job_run_history import JobRunHistory


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Create a test database session."""
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_get_last_success_returns_latest_successful_run(db_session: Session) -> None:
    """get_last_success returns the most recent run with success=true."""
    t0 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 3, 1, 11, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)

    db_session.add(JobRunHistory(job_name="test_job", run_at=t0, success=True, error_message=None))
    db_session.add(JobRunHistory(job_name="test_job", run_at=t1, success=False, error_message="err"))
    db_session.add(JobRunHistory(job_name="test_job", run_at=t2, success=True, error_message=None))
    db_session.commit()

    repo = JobExecutionRepository(db_session)
    last_success = repo.get_last_success("test_job")
    assert last_success is not None
    assert last_success == t2


def test_get_last_success_none_when_no_successful_runs(db_session: Session) -> None:
    """get_last_success returns None when all runs failed."""
    t0 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    db_session.add(JobRunHistory(job_name="test_job", run_at=t0, success=False, error_message="err"))
    db_session.commit()

    repo = JobExecutionRepository(db_session)
    assert repo.get_last_success("test_job") is None


def test_get_last_success_naive_datetime_normalized(db_session: Session) -> None:
    """Naive datetime from SQLite is normalized to UTC-aware."""
    # SQLite may return naive datetimes; we treat them as UTC
    t_naive = datetime(2026, 3, 1, 10, 0, 0)  # no tzinfo
    db_session.add(JobRunHistory(job_name="test_job", run_at=t_naive, success=True, error_message=None))
    db_session.commit()

    repo = JobExecutionRepository(db_session)
    last_success = repo.get_last_success("test_job")
    assert last_success is not None
    assert last_success.tzinfo is not None


def test_list_recent_runs_all_jobs(db_session: Session) -> None:
    """list_recent_runs with job_name=None returns all jobs ordered by run_at desc."""
    t0 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 3, 1, 11, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)

    db_session.add(JobRunHistory(job_name="job_a", run_at=t0, success=True, error_message=None))
    db_session.add(JobRunHistory(job_name="job_b", run_at=t1, success=True, error_message=None))
    db_session.add(JobRunHistory(job_name="job_a", run_at=t2, success=True, error_message=None))
    db_session.commit()

    repo = JobExecutionRepository(db_session)
    runs = repo.list_recent_runs(job_name=None, limit=10)
    assert len(runs) == 3
    # SQLite may return naive datetimes; compare timestamps
    def _ts(dt: datetime) -> float:
        d = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        return d.timestamp()

    assert _ts(runs[0].run_at) == _ts(t2)
    assert _ts(runs[1].run_at) == _ts(t1)
    assert _ts(runs[2].run_at) == _ts(t0)


def test_list_recent_runs_filter_by_job(db_session: Session) -> None:
    """list_recent_runs with job_name filters to that job only."""
    t0 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 3, 1, 11, 0, 0, tzinfo=timezone.utc)
    db_session.add(JobRunHistory(job_name="job_a", run_at=t0, success=True, error_message=None))
    db_session.add(JobRunHistory(job_name="job_b", run_at=t1, success=True, error_message=None))
    db_session.commit()

    repo = JobExecutionRepository(db_session)
    runs_a = repo.list_recent_runs(job_name="job_a", limit=10)
    assert len(runs_a) == 1
    assert runs_a[0].job_name == "job_a"
    # SQLite may return naive datetimes; normalize for comparison
    rt = runs_a[0].run_at
    rt_utc = rt.replace(tzinfo=timezone.utc) if rt.tzinfo is None else rt.astimezone(timezone.utc)
    assert abs((rt_utc - t0).total_seconds()) < 1


def test_record_run_with_success_and_error(db_session: Session) -> None:
    """record_run stores success and error_message."""
    repo = JobExecutionRepository(db_session)
    t0 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    repo.record_run("test_job", t0, success=False, error_message="oops")
    db_session.commit()

    runs = repo.list_recent_runs(job_name="test_job", limit=1)
    assert len(runs) == 1
    assert runs[0].success is False
    assert runs[0].error_message == "oops"
