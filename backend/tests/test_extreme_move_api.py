"""Integration tests for extreme move read-only API (016)."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.data.database import Base, get_session
from backend.app.main import create_app
from backend.app.models.extreme_move_event import ExtremeMoveEvent
from backend.app.models.stock import Stock


def _create_test_app() -> tuple[TestClient, Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestSessionLocal()
    app = create_app(omit_scheduler=True)

    def override_get_session():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app), session


@pytest.mark.integration
def test_extreme_move_events_empty() -> None:
    client, _db = _create_test_app()
    resp = client.get("/api/extreme-move/events")
    assert resp.status_code == 200
    data = resp.json()
    assert data["events"] == []
    assert data["total"] == 0


@pytest.mark.integration
def test_extreme_move_events_list_and_filter() -> None:
    client, db = _create_test_app()
    db.add(Stock(symbol="AAA", name="A", sector="Tech", market_cap=None))
    db.commit()
    ev = ExtremeMoveEvent(
        symbol="AAA",
        event_date=date(2024, 3, 15),
        return_pct=6.5,
        event_type="extreme_up",
        created_at=datetime.now(timezone.utc),
    )
    db.add(ev)
    db.commit()

    r = client.get("/api/extreme-move/events")
    assert r.status_code == 200
    assert r.json()["total"] == 1

    r2 = client.get("/api/extreme-move/events?event_type=extreme_down")
    assert r2.json()["total"] == 0

    r3 = client.get("/api/extreme-move/events?event_type=extreme_up")
    assert r3.json()["total"] == 1


@pytest.mark.integration
def test_extreme_move_events_invalid_date() -> None:
    client, _db = _create_test_app()
    resp = client.get("/api/extreme-move/events?since_date=not-a-date")
    assert resp.status_code == 400
    body = resp.json()
    assert body.get("detail", {}).get("error_type") == "VALIDATION_ERROR"


@pytest.mark.integration
def test_extreme_move_evaluation_summary_empty() -> None:
    client, _db = _create_test_app()
    resp = client.get("/api/extreme-move/evaluation/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_events"] == 0
    assert data["by_horizon"]["1d"]["evaluable_count"] == 0


@pytest.mark.integration
def test_extreme_move_evaluation_by_magnitude_empty() -> None:
    client, _db = _create_test_app()
    resp = client.get("/api/extreme-move/evaluation/by-magnitude")
    assert resp.status_code == 200
    assert resp.json()["by_magnitude"] == {}


@pytest.mark.integration
def test_extreme_move_evaluation_by_magnitude_with_event() -> None:
    client, db = _create_test_app()
    db.add(Stock(symbol="BBB", name="B", sector="Tech", market_cap=None))
    db.commit()
    ev = ExtremeMoveEvent(
        symbol="BBB",
        event_date=date(2024, 3, 15),
        return_pct=6.5,
        event_type="extreme_up",
        magnitude_bucket="5-8",
        volume_bucket="high",
        created_at=datetime.now(timezone.utc),
    )
    db.add(ev)
    db.commit()
    resp = client.get("/api/extreme-move/evaluation/by-magnitude")
    assert resp.status_code == 200
    body = resp.json()
    assert "5-8" in body["by_magnitude"]
    assert body["by_magnitude"]["5-8"]["total_events"] == 1


@pytest.mark.integration
def test_extreme_move_evaluation_by_magnitude_volume() -> None:
    client, db = _create_test_app()
    db.add(Stock(symbol="CCC", name="C", sector="Tech", market_cap=None))
    db.commit()
    ev = ExtremeMoveEvent(
        symbol="CCC",
        event_date=date(2024, 4, 1),
        return_pct=-6.0,
        event_type="extreme_down",
        magnitude_bucket="5-8",
        volume_bucket="extreme",
        created_at=datetime.now(timezone.utc),
    )
    db.add(ev)
    db.commit()
    resp = client.get("/api/extreme-move/evaluation/by-magnitude-volume")
    assert resp.status_code == 200
    assert "5-8|extreme" in resp.json()["by_magnitude_volume"]


@pytest.mark.integration
def test_extreme_move_events_include_context_fields() -> None:
    client, db = _create_test_app()
    db.add(Stock(symbol="DDD", name="D", sector="Tech", market_cap=None))
    db.commit()
    db.add(
        ExtremeMoveEvent(
            symbol="DDD",
            event_date=date(2024, 5, 1),
            return_pct=7.0,
            event_type="extreme_up",
            magnitude_bucket="5-8",
            volume_ratio=2.5,
            volume_bucket="high",
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    r = client.get("/api/extreme-move/events")
    assert r.status_code == 200
    ev = r.json()["events"][0]
    assert ev["magnitude_bucket"] == "5-8"
    assert ev["volume_ratio"] == 2.5
    assert ev["volume_bucket"] == "high"
