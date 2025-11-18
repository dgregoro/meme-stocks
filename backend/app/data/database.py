from __future__ import annotations

from typing import Generator
import os

from sqlalchemy import create_engine
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
SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=Session
)


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


def init_db() -> None:
    """Initialize database schema if missing (development convenience)."""
    Base.metadata.create_all(bind=engine)
