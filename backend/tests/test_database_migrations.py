"""Tests for database migrations (add-column-if-missing style)."""

from __future__ import annotations

import os
import tempfile

import pytest

from backend.app.data.database import engine

_db_url = str(engine.url)


def test_migrate_metrics_summary_does_not_create_new_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Migration must not create a new DB file when path does not exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        nonexistent = os.path.join(tmpdir, "does_not_exist_yet.db")
        assert not os.path.exists(nonexistent)

        from backend.app.data import database

        orig_url = database._db_url
        database._db_url = f"sqlite:///{nonexistent}"
        try:
            database._migrate_job_run_history_add_metrics_and_summary()
        finally:
            database._db_url = orig_url

        assert not os.path.exists(nonexistent)


def test_migrate_metrics_summary_adds_columns_when_file_exists() -> None:
    """When sqlite file exists with job_run_history table, migration adds columns."""
    import sqlite3

    from sqlalchemy import create_engine

    from backend.app.data.database import Base
    from backend.app.models.job_run_history import JobRunHistory  # noqa: F401 - for table

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.db")
        url = f"sqlite:///{path}"
        test_engine = create_engine(url, future=True)
        Base.metadata.create_all(bind=test_engine)

        from backend.app.data import database

        orig_url = database._db_url
        orig_engine = database.engine
        database._db_url = url
        database.engine = test_engine
        try:
            database._migrate_job_run_history_add_metrics_and_summary()
        finally:
            database._db_url = orig_url
            database.engine = orig_engine

        conn = sqlite3.connect(path)
        cur = conn.execute("PRAGMA table_info(job_run_history)")
        columns = {row[1] for row in cur.fetchall()}
        conn.close()
        assert "metrics_json" in columns
        assert "summary" in columns


def test_migrate_extreme_move_context_adds_columns() -> None:
    """Old extreme_move_events table without context columns gets ALTERs."""
    import sqlite3

    from sqlalchemy import create_engine

    from backend.app.data import database

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "emigrate.db")
        url = f"sqlite:///{path}"
        conn = sqlite3.connect(path)
        conn.execute(
            """
            CREATE TABLE extreme_move_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol VARCHAR(16) NOT NULL,
                event_date DATE NOT NULL,
                return_pct FLOAT NOT NULL,
                event_type VARCHAR(32) NOT NULL,
                created_at DATETIME NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()
        test_engine = create_engine(url, future=True)
        orig_url = database._db_url
        orig_engine = database.engine
        database._db_url = url
        database.engine = test_engine
        try:
            database._migrate_extreme_move_context_fields()
        finally:
            database._db_url = orig_url
            database.engine = orig_engine

        conn = sqlite3.connect(path)
        cur = conn.execute("PRAGMA table_info(extreme_move_events)")
        cols = {row[1] for row in cur.fetchall()}
        conn.close()
        assert "magnitude_bucket" in cols
        assert "volume_ratio" in cols
        assert "volume_bucket" in cols


def test_migrate_drop_legacy_reddit_tables() -> None:
    """Legacy Reddit tables are dropped when present on SQLite file DBs."""
    import sqlite3

    from sqlalchemy import create_engine

    from backend.app.data import database

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "reddit_drop.db")
        url = f"sqlite:///{path}"
        conn = sqlite3.connect(path)
        conn.execute(
            """
            CREATE TABLE reddit_posts (
                id VARCHAR(32) PRIMARY KEY
            )
            """
        )
        conn.execute("CREATE TABLE reddit_symbol_mentions (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE reddit_daily_features (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()
        test_engine = create_engine(url, future=True)
        orig_url = database._db_url
        orig_engine = database.engine
        database._db_url = url
        database.engine = test_engine
        try:
            database._migrate_drop_legacy_reddit_tables()
        finally:
            database._db_url = orig_url
            database.engine = orig_engine

        conn = sqlite3.connect(path)
        names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert "reddit_posts" not in names
        assert "reddit_symbol_mentions" not in names
        assert "reddit_daily_features" not in names
