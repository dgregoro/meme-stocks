"""Tests for JobExecutionRepository: last_run, last_success, list_recent_runs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.app.data.repositories.job_execution_repo import JobExecutionRepository
from backend.app.models.job_run_history import JobRunHistory


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


def test_list_recent_runs_filter_by_job_names(db_session: Session) -> None:
    """list_recent_runs with job_names filters to the union of those jobs."""
    t0 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 3, 1, 11, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    db_session.add(JobRunHistory(job_name="job_a", run_at=t0, success=True, error_message=None))
    db_session.add(JobRunHistory(job_name="job_b", run_at=t1, success=True, error_message=None))
    db_session.add(JobRunHistory(job_name="job_c", run_at=t2, success=True, error_message=None))
    db_session.commit()

    repo = JobExecutionRepository(db_session)
    runs = repo.list_recent_runs(limit=10, job_names=("job_a", "job_c"))
    assert len(runs) == 2
    assert {r.job_name for r in runs} == {"job_a", "job_c"}


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


def test_one_run_produces_one_history_row(db_session: Session) -> None:
    """One successful job execution produces exactly one JobRunHistory row (no duplicates)."""
    repo = JobExecutionRepository(db_session)
    t0 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    started = t0 - timedelta(seconds=5)
    repo.record_run(
        "reddit_collection",
        run_at=t0,
        success=True,
        started_at=started,
        duration_seconds=5.0,
    )
    db_session.commit()

    runs = repo.list_recent_runs(job_name="reddit_collection", limit=10)
    assert len(runs) == 1
    assert runs[0].started_at is not None
    assert runs[0].duration_seconds == 5.0


def test_record_run_persists_timing_fields(db_session: Session) -> None:
    """record_run persists started_at and duration_seconds on the JobRunHistory row."""
    repo = JobExecutionRepository(db_session)
    t0 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    started = t0 - timedelta(seconds=12)
    history = repo.record_run(
        "price_collection",
        run_at=t0,
        success=True,
        started_at=started,
        duration_seconds=12.5,
    )
    db_session.commit()

    assert history.job_name == "price_collection"
    assert history.run_at is not None
    assert history.started_at is not None
    assert history.duration_seconds == 12.5

    runs = repo.list_recent_runs(job_name="price_collection", limit=1)
    assert len(runs) == 1
    assert runs[0].started_at is not None
    assert runs[0].duration_seconds == 12.5
    # SQLite may return naive; normalize for comparison
    rt = runs[0].started_at.replace(tzinfo=timezone.utc) if runs[0].started_at.tzinfo is None else runs[0].started_at
    assert abs((rt - started).total_seconds()) < 1


def test_record_run_persists_summary_and_metrics(db_session: Session) -> None:
    """record_run persists summary and metrics_json on the JobRunHistory row."""
    repo = JobExecutionRepository(db_session)
    t0 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    summary = "reddit: inserted 12 posts (50 fetched), symbols=8"
    metrics = {"posts_fetched": 50, "posts_inserted": 12, "symbols_mentioned": 8}
    history = repo.record_run(
        "reddit_collection",
        run_at=t0,
        success=True,
        summary=summary,
        metrics=metrics,
    )
    db_session.commit()

    assert history.summary == summary
    assert history.metrics_json is not None
    import json

    parsed = json.loads(history.metrics_json)
    assert parsed == {"posts_fetched": 50, "posts_inserted": 12, "symbols_mentioned": 8}

    runs = repo.list_recent_runs(job_name="reddit_collection", limit=1)
    assert len(runs) == 1
    assert runs[0].summary == summary


def test_record_run_truncates_long_summary(db_session: Session) -> None:
    """record_run truncates summary to 240 chars."""
    repo = JobExecutionRepository(db_session)
    t0 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    long_summary = "x" * 300
    history = repo.record_run(
        "test_job",
        run_at=t0,
        success=True,
        summary=long_summary,
    )
    db_session.commit()
    assert len(history.summary or "") == 240
    assert history.summary is not None and history.summary.endswith("…")
