"""Database connection, session management, and schema initialization."""

from __future__ import annotations

from typing import Generator
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from backend.app.config import get_settings


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
engine = create_engine(_db_url, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)


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
    except Exception:
        pass  # Non-SQLite or migration not supported; rely on create_all


def init_db() -> None:
    """Initialize database schema if missing (development convenience)."""
    Base.metadata.create_all(bind=engine)
    _migrate_drop_reddit_posts_stock_symbol()
