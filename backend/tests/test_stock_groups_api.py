"""Tests for stock groups read-only API."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import create_app
from backend.app.data.database import Base, get_session
from backend.app.models.stock import Stock
from backend.app.models.stock_group import StockGroup


def _create_test_app() -> tuple[TestClient, Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()

    app = create_app(omit_scheduler=True)

    def override_get_session():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app), session


def test_list_stock_groups_empty() -> None:
    """GET /api/stock-groups returns is_empty true when no groups."""
    client, _ = _create_test_app()
    resp = client.get("/api/stock-groups")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_empty"] is True
    assert data["total_rows"] == 0
    assert data["groups"] == []


def test_list_stock_groups_populated() -> None:
    """GET /api/stock-groups returns groups and counts when populated."""
    client, session = _create_test_app()
    session.add(Stock(symbol="GME", name="GameStop", sector=None, market_cap=None))
    session.add(Stock(symbol="AMC", name="AMC", sector=None, market_cap=None))
    session.flush()
    session.add(StockGroup(group_id="meme", stock_symbol="GME"))
    session.add(StockGroup(group_id="meme", stock_symbol="AMC"))
    session.commit()

    resp = client.get("/api/stock-groups")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_empty"] is False
    assert data["total_rows"] == 2
    assert len(data["groups"]) == 1
    assert data["groups"][0]["group_id"] == "meme"
    assert data["groups"][0]["symbol_count"] == 2


def test_get_stock_group_detail() -> None:
    """GET /api/stock-groups/{group_id} returns symbols in group."""
    client, session = _create_test_app()
    session.add(Stock(symbol="GME", name="GameStop", sector=None, market_cap=None))
    session.add(Stock(symbol="AMC", name="AMC", sector=None, market_cap=None))
    session.flush()
    session.add(StockGroup(group_id="meme", stock_symbol="GME"))
    session.add(StockGroup(group_id="meme", stock_symbol="AMC"))
    session.commit()

    resp = client.get("/api/stock-groups/meme")
    assert resp.status_code == 200
    data = resp.json()
    assert data["group_id"] == "meme"
    assert data["symbol_count"] == 2
    assert set(data["symbols"]) == {"GME", "AMC"}


def test_get_stock_group_not_found() -> None:
    """GET /api/stock-groups/{group_id} returns 404 for unknown group."""
    client, _ = _create_test_app()
    resp = client.get("/api/stock-groups/nonexistent")
    assert resp.status_code == 404
