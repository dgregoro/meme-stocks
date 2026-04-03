"""Pytest fixtures: isolated in-memory SQLite so tests never wipe ``data/app.db``."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.data.database import Base, get_session
from backend.app.main import create_app
from backend.app.services.scheduler_service import SchedulerService


@pytest.fixture
def isolated_sqlite_engine() -> Generator[Engine, None, None]:
    """Fresh in-memory DB per test function; all ORM tables created then dropped."""
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(isolated_sqlite_engine: Engine) -> Generator[Session, None, None]:
    """Session bound to isolated engine (for repository / service tests)."""
    SessionFactory = sessionmaker(
        bind=isolated_sqlite_engine,
        autocommit=False,
        autoflush=False,
    )
    db = SessionFactory()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_app(
    isolated_sqlite_engine: Engine,
) -> Generator[tuple[FastAPI, MagicMock, TestClient], None, None]:
    """FastAPI app + TestClient: mock scheduler, isolated DB for lifespan and ``get_session``."""
    MainSession = sessionmaker(
        bind=isolated_sqlite_engine,
        autocommit=False,
        autoflush=False,
    )

    def override_get_session() -> Generator[Session, None, None]:
        db = MainSession()
        try:
            yield db
        finally:
            db.close()

    with patch("backend.app.main.init_db"), patch("backend.app.main.SessionLocal", MainSession):
        mock_scheduler = MagicMock(spec=SchedulerService)
        app = create_app(scheduler_for_testing=mock_scheduler)
        app.dependency_overrides[get_session] = override_get_session
        with TestClient(app) as client:
            yield app, mock_scheduler, client
        app.dependency_overrides.clear()


@pytest.fixture
def test_app_omit_scheduler(
    isolated_sqlite_engine: Engine,
) -> Generator[tuple[FastAPI, TestClient], None, None]:
    """Like ``test_app`` but ``omit_scheduler=True`` (e.g. jobs 503 test)."""
    MainSession = sessionmaker(
        bind=isolated_sqlite_engine,
        autocommit=False,
        autoflush=False,
    )

    def override_get_session() -> Generator[Session, None, None]:
        db = MainSession()
        try:
            yield db
        finally:
            db.close()

    with patch("backend.app.main.init_db"), patch("backend.app.main.SessionLocal", MainSession):
        app = create_app(omit_scheduler=True)
        app.dependency_overrides[get_session] = override_get_session
        with TestClient(app) as client:
            yield app, client
        app.dependency_overrides.clear()


@pytest.fixture
def isolated_omit_scheduler_client(
    isolated_sqlite_engine: Engine,
) -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    """TestClient with ``omit_scheduler=True`` and API deps on the same isolated engine."""
    MainSession = sessionmaker(
        bind=isolated_sqlite_engine,
        autocommit=False,
        autoflush=False,
    )

    def override_get_session() -> Generator[Session, None, None]:
        db = MainSession()
        try:
            yield db
        finally:
            db.close()

    with patch("backend.app.main.init_db"), patch("backend.app.main.SessionLocal", MainSession):
        app = create_app(omit_scheduler=True)
        app.dependency_overrides[get_session] = override_get_session
        with TestClient(app) as client:
            yield client, MainSession
        app.dependency_overrides.clear()
