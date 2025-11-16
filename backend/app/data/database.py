from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from backend.app.config import get_settings


Base = declarative_base()


def _build_engine_url() -> str:
    settings = get_settings()
    return settings.database_url


engine = create_engine(_build_engine_url(), future=True)
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
