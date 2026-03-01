"""Tests for job lock repository (acquire, heartbeat, release, get_lock)."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.data.database import Base
from backend.app.models import job_lock  # noqa: F401 - register JobLock with Base
from backend.app.data.repositories.job_lock_repo import JobLockRepository


@pytest.mark.integration
def test_job_lock_acquire_succeeds_when_empty() -> None:
    """Acquire succeeds when no row exists."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        repo = JobLockRepository(db)
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        got = repo.try_acquire_lock("test_lock", "owner1", ttl_seconds=60, now=now)
        assert got is True
        db.commit()
        row = repo.get_lock("test_lock")
        assert row is not None
        assert row.owner == "owner1"
        # SQLite may return naive datetime; compare timestamps
        exp = row.expires_at.replace(tzinfo=timezone.utc) if row.expires_at and row.expires_at.tzinfo is None else row.expires_at
        assert exp == now + timedelta(seconds=60)
    finally:
        db.close()


@pytest.mark.integration
def test_job_lock_acquire_fails_when_not_expired() -> None:
    """Acquire returns False when another owner holds and lock is not expired."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        repo = JobLockRepository(db)
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        repo.try_acquire_lock("test_lock", "owner1", ttl_seconds=60, now=now)
        db.commit()

        got = repo.try_acquire_lock("test_lock", "owner2", ttl_seconds=60, now=now)
        assert got is False
        current = repo.get_lock("test_lock")
        assert current is not None
        assert current.owner == "owner1"

        later = now + timedelta(seconds=30)
        got2 = repo.try_acquire_lock("test_lock", "owner2", ttl_seconds=60, now=later)
        assert got2 is False
    finally:
        db.close()


@pytest.mark.integration
def test_job_lock_acquire_succeeds_when_expired() -> None:
    """Acquire succeeds when existing row has expires_at <= now."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        repo = JobLockRepository(db)
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        repo.try_acquire_lock("test_lock", "owner1", ttl_seconds=60, now=now)
        db.commit()

        after_expiry = now + timedelta(seconds=61)
        got = repo.try_acquire_lock("test_lock", "owner2", ttl_seconds=120, now=after_expiry)
        assert got is True
        db.commit()
        row = repo.get_lock("test_lock")
        assert row is not None
        assert row.owner == "owner2"
        exp = row.expires_at.replace(tzinfo=timezone.utc) if row.expires_at and row.expires_at.tzinfo is None else row.expires_at
        assert exp == after_expiry + timedelta(seconds=120)
    finally:
        db.close()


@pytest.mark.integration
def test_job_lock_release_only_works_for_owner() -> None:
    """Release deletes only when owner matches; returns False otherwise."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        repo = JobLockRepository(db)
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        repo.try_acquire_lock("test_lock", "owner1", ttl_seconds=60, now=now)
        db.commit()

        released = repo.release_lock("test_lock", "owner2")
        assert released is False
        assert repo.get_lock("test_lock") is not None

        released = repo.release_lock("test_lock", "owner1")
        assert released is True
        db.commit()
        assert repo.get_lock("test_lock") is None
    finally:
        db.close()


@pytest.mark.integration
def test_job_lock_heartbeat_extends_expires_only_for_owner() -> None:
    """Heartbeat updates heartbeat_at and extends expires_at only when owner matches."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        repo = JobLockRepository(db)
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        repo.try_acquire_lock("test_lock", "owner1", ttl_seconds=60, now=now)
        db.commit()

        later = now + timedelta(seconds=30)
        ok = repo.heartbeat("test_lock", "owner1", ttl_seconds=60, now=later)
        assert ok is True
        db.commit()
        row = repo.get_lock("test_lock")
        assert row is not None
        assert row.heartbeat_at == later or (row.heartbeat_at and row.heartbeat_at.replace(tzinfo=timezone.utc) == later)
        exp = row.expires_at.replace(tzinfo=timezone.utc) if row.expires_at and row.expires_at.tzinfo is None else row.expires_at
        assert exp == later + timedelta(seconds=60)

        ok2 = repo.heartbeat("test_lock", "owner2", ttl_seconds=60, now=later)
        assert ok2 is False
        current = repo.get_lock("test_lock")
        assert current is not None
        assert current.owner == "owner1"
    finally:
        db.close()
