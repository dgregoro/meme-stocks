"""Database connection, session management, and schema initialization."""

from __future__ import annotations

import logging
import os
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from backend.app.config import get_settings

logger = logging.getLogger(__name__)

Base = declarative_base()


def _build_engine_url() -> str:
    settings = get_settings()
    return settings.database_url


def _ensure_sqlite_path_exists(db_url: str) -> None:
    if db_url.startswith("sqlite:///"):
        path = db_url.replace("sqlite:///", "", 1)
        if path and path != ":memory:":
            directory = os.path.dirname(os.path.abspath(path))
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)


_db_url = _build_engine_url()
_ensure_sqlite_path_exists(_db_url)
_connect_args: dict[str, object] = {}
if "sqlite" in _db_url.lower():
    # SQLite defaults to busy_timeout=0 (fail immediately on lock).
    _connect_args["timeout"] = 30  # Wait up to 30s when DB locked (scheduler + API concurrency)
engine = create_engine(_db_url, future=True, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)


@event.listens_for(engine, "connect")
def _sqlite_connect(dbapi_conn: object, connection_record: object) -> None:
    """Enable WAL mode and busy timeout for SQLite (file DBs only) to reduce 'database is locked'."""
    if "sqlite" in _db_url.lower() and ":memory:" not in _db_url:
        cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")  # 30s in ms
        cursor.close()


def get_session() -> Generator[Session, None, None]:
    """Yield a database session for use in request/worker contexts.

    In FastAPI, this will typically be used as a dependency. The session is
    always closed, and any unexpected SQLAlchemy errors should be handled by
    callers; we intentionally do not swallow them here.
    """

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_paper_trades_add_option_columns() -> None:
    """Add option-related columns to paper_trades if they do not exist."""
    import sqlite3

    if ":memory:" in _db_url or "sqlite" not in _db_url.lower():
        return
    path = _db_url.replace("sqlite:///", "", 1).split("?")[0].strip()
    if not path or path == ":memory:":
        return
    path = os.path.abspath(path)
    try:
        conn = sqlite3.connect(path)
        cur = conn.execute("PRAGMA table_info(paper_trades)")
        columns = {row[1] for row in cur.fetchall()}
        conn.close()
        with engine.begin() as c:
            if "instrument_type" not in columns:
                c.execute(
                    text("ALTER TABLE paper_trades ADD COLUMN instrument_type VARCHAR(16) DEFAULT 'stock' NOT NULL")
                )
            if "option_type" not in columns:
                c.execute(text("ALTER TABLE paper_trades ADD COLUMN option_type VARCHAR(8)"))
            if "strike_price" not in columns:
                c.execute(text("ALTER TABLE paper_trades ADD COLUMN strike_price FLOAT"))
            if "expiry_date" not in columns:
                c.execute(text("ALTER TABLE paper_trades ADD COLUMN expiry_date DATE"))
    except Exception as exc:
        logger.warning(
            "Migration paper_trades option columns failed: %s",
            exc,
        )


def _migrate_job_run_history_add_success_columns() -> None:
    """Add success and error_message to job_run_history if they do not exist."""
    import sqlite3

    if ":memory:" in _db_url or "sqlite" not in _db_url.lower():
        return
    path = _db_url.replace("sqlite:///", "", 1).split("?")[0].strip()
    if not path or path == ":memory:":
        return
    path = os.path.abspath(path)
    try:
        conn = sqlite3.connect(path)
        cur = conn.execute("PRAGMA table_info(job_run_history)")
        columns = {row[1] for row in cur.fetchall()}
        conn.close()
        with engine.begin() as c:
            if "success" not in columns:
                c.execute(text("ALTER TABLE job_run_history ADD COLUMN success BOOLEAN NOT NULL DEFAULT 1"))
            if "error_message" not in columns:
                c.execute(text("ALTER TABLE job_run_history ADD COLUMN error_message VARCHAR(500)"))
            if "started_at" not in columns:
                c.execute(text("ALTER TABLE job_run_history ADD COLUMN started_at DATETIME"))
            if "duration_seconds" not in columns:
                c.execute(text("ALTER TABLE job_run_history ADD COLUMN duration_seconds FLOAT"))
    except Exception as exc:
        logger.warning(
            "Migration job_run_history success columns failed: %s",
            exc,
        )


def _migrate_job_run_history_add_metrics_and_summary() -> None:
    """Add metrics_json and summary to job_run_history if they do not exist."""
    import sqlite3

    if ":memory:" in _db_url or "sqlite" not in _db_url.lower():
        return
    path = _db_url.replace("sqlite:///", "", 1).split("?")[0].strip()
    if not path or path == ":memory:":
        return
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return
    try:
        conn = sqlite3.connect(path)
        cur = conn.execute("PRAGMA table_info(job_run_history)")
        columns = {row[1] for row in cur.fetchall()}
        conn.close()
        with engine.begin() as c:
            if "metrics_json" not in columns:
                c.execute(text("ALTER TABLE job_run_history ADD COLUMN metrics_json TEXT"))
            if "summary" not in columns:
                c.execute(text("ALTER TABLE job_run_history ADD COLUMN summary TEXT"))
    except Exception as exc:
        logger.warning(
            "Migration job_run_history metrics/summary columns failed: %s",
            exc,
        )


def _migrate_notifications_add_signal_metadata() -> None:
    """Add signal_metadata column to notifications for combined-signal alert metadata."""
    import sqlite3

    if ":memory:" in _db_url or "sqlite" not in _db_url.lower():
        return
    path = _db_url.replace("sqlite:///", "", 1).split("?")[0].strip()
    if not path or path == ":memory:":
        return
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return
    try:
        conn = sqlite3.connect(path)
        cur = conn.execute("PRAGMA table_info(notifications)")
        columns = {row[1] for row in cur.fetchall()}
        conn.close()
        with engine.begin() as c:
            if "signal_metadata" not in columns:
                c.execute(text("ALTER TABLE notifications ADD COLUMN signal_metadata TEXT"))
    except Exception as exc:
        logger.warning(
            "Migration notifications signal_metadata failed: %s",
            exc,
        )


def _migrate_leader_events_add_job_run_id() -> None:
    """Add job_run_id to leader_events for run traceability."""
    import sqlite3

    if ":memory:" in _db_url or "sqlite" not in _db_url.lower():
        return
    path = _db_url.replace("sqlite:///", "", 1).split("?")[0].strip()
    if not path or path == ":memory:":
        return
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return
    try:
        conn = sqlite3.connect(path)
        cur = conn.execute("PRAGMA table_info(leader_events)")
        columns = {row[1] for row in cur.fetchall()}
        conn.close()
        with engine.begin() as c:
            if "job_run_id" not in columns:
                c.execute(
                    text("ALTER TABLE leader_events ADD COLUMN job_run_id INTEGER REFERENCES job_run_history(id)")
                )
    except Exception as exc:
        logger.warning(
            "Migration leader_events job_run_id failed: %s",
            exc,
        )


def _migrate_create_leader_follower_candidates() -> None:
    """Create leader_follower_candidates table if it does not exist."""
    import sqlite3

    if ":memory:" in _db_url or "sqlite" not in _db_url.lower():
        return
    path = _db_url.replace("sqlite:///", "", 1).split("?")[0].strip()
    if not path or path == ":memory:":
        return
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return
    try:
        conn = sqlite3.connect(path)
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='leader_follower_candidates'")
        if cur.fetchone() is None:
            conn.execute(
                """
                CREATE TABLE leader_follower_candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_run_id INTEGER NOT NULL REFERENCES job_run_history(id),
                    event_date DATE NOT NULL,
                    leader_symbol VARCHAR(16) NOT NULL REFERENCES stocks(symbol),
                    follower_symbol VARCHAR(16) NOT NULL REFERENCES stocks(symbol),
                    group_id VARCHAR(64) NOT NULL,
                    metrics_json TEXT,
                    created_at DATETIME
                )
                """
            )
            conn.execute(
                "CREATE INDEX ix_leader_follower_candidates_job_run_id ON leader_follower_candidates(job_run_id)"
            )
            conn.execute(
                "CREATE INDEX ix_leader_follower_candidates_event_date ON leader_follower_candidates(event_date)"
            )
            conn.execute(
                "CREATE INDEX ix_leader_follower_candidates_leader_symbol ON leader_follower_candidates(leader_symbol)"
            )
            conn.execute(
                "CREATE INDEX ix_leader_follower_candidates_follower_symbol ON leader_follower_candidates(follower_symbol)"
            )
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.warning(
            "Migration leader_follower_candidates failed: %s",
            exc,
        )


def _migrate_create_leader_debug_evaluations() -> None:
    """Create leader_debug_evaluations table if it does not exist."""
    import sqlite3

    if ":memory:" in _db_url or "sqlite" not in _db_url.lower():
        return
    path = _db_url.replace("sqlite:///", "", 1).split("?")[0].strip()
    if not path or path == ":memory:":
        return
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return
    try:
        conn = sqlite3.connect(path)
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='leader_debug_evaluations'")
        if cur.fetchone() is None:
            conn.execute(
                """
                CREATE TABLE leader_debug_evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_run_id INTEGER NOT NULL REFERENCES job_run_history(id),
                    stock_symbol VARCHAR(16) NOT NULL,
                    return_pct REAL,
                    volume_ratio REAL,
                    qualified_as_leader INTEGER NOT NULL,
                    rejection_reasons TEXT NOT NULL,
                    metrics_json TEXT,
                    created_at DATETIME,
                    UNIQUE(job_run_id, stock_symbol)
                )
                """
            )
            conn.execute(
                "CREATE INDEX ix_leader_debug_evaluations_job_run_id " "ON leader_debug_evaluations(job_run_id)"
            )
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.warning(
            "Migration leader_debug_evaluations failed: %s",
            exc,
        )


def _migrate_drop_reddit_posts_stock_symbol() -> None:
    """Drop legacy stock_symbol column from reddit_posts if it exists.

    The model now uses RedditSymbolMention junction table; old schemas may
    have a NOT NULL stock_symbol column that causes insert failures.
    """
    import sqlite3

    if ":memory:" in _db_url or "sqlite" not in _db_url.lower():
        return
    path = _db_url.replace("sqlite:///", "", 1).split("?")[0].strip()
    if not path or path == ":memory:":
        return
    path = os.path.abspath(path)
    try:
        conn = sqlite3.connect(path)
        cur = conn.execute("PRAGMA table_info(reddit_posts)")
        columns = [row[1] for row in cur.fetchall()]
        conn.close()
        if "stock_symbol" in columns:
            with engine.begin() as c:
                c.execute(text("ALTER TABLE reddit_posts DROP COLUMN stock_symbol"))
    except Exception as exc:
        logger.warning(
            "Migration drop reddit_posts.stock_symbol failed (non-SQLite or unsupported): %s",
            exc,
        )


def _migrate_create_job_locks_if_missing() -> None:
    """Create job_locks table if missing (e.g. DB created before job_lock model existed)."""
    if ":memory:" in _db_url or "sqlite" not in _db_url.lower():
        return
    path = _db_url.replace("sqlite:///", "", 1).split("?")[0].strip()
    if not path or path == ":memory:":
        return
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return
    try:
        with engine.begin() as c:
            c.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS job_locks ("
                    "name VARCHAR(128) NOT NULL PRIMARY KEY, "
                    "owner TEXT NOT NULL, "
                    "acquired_at DATETIME NOT NULL, "
                    "expires_at DATETIME NOT NULL, "
                    "heartbeat_at DATETIME NOT NULL)"
                )
            )
    except Exception as exc:
        logger.warning("Migration create job_locks failed: %s", exc)


def init_db() -> None:
    """Initialize database schema if missing (development convenience)."""
    Base.metadata.create_all(bind=engine)
    _migrate_create_job_locks_if_missing()
    _migrate_job_run_history_add_success_columns()
    _migrate_job_run_history_add_metrics_and_summary()
    _migrate_drop_reddit_posts_stock_symbol()
    _migrate_paper_trades_add_option_columns()
    _migrate_notifications_add_signal_metadata()
    _migrate_leader_events_add_job_run_id()
    _migrate_create_leader_follower_candidates()
    _migrate_create_leader_debug_evaluations()
