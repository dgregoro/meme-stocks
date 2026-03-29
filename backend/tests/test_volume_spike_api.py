"""Integration tests for volume spike read-only API."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.data.database import Base, get_session
from backend.app.main import create_app
from backend.app.models.stock import Stock
from backend.app.models.volume_spike_event import VolumeSpikeEvent


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
def test_volume_spike_events_empty() -> None:
    client, _db = _create_test_app()
    resp = client.get("/api/volume-spike/events")
    assert resp.status_code == 200
    data = resp.json()
    assert data["events"] == []
    assert data["total"] == 0


@pytest.mark.integration
def test_volume_spike_events_list_and_filter() -> None:
    client, db = _create_test_app()
    db.add(Stock(symbol="AAA", name="A", sector="Tech", market_cap=None))
    db.commit()
    ev = VolumeSpikeEvent(
        symbol="AAA",
        event_date=date(2024, 3, 15),
        volume=1_000_000,
        baseline_volume=300_000.0,
        volume_ratio=3.33,
        same_day_return_pct=0.6,
        event_type="spike_up",
        created_at=datetime.now(timezone.utc),
    )
    db.add(ev)
    db.commit()

    r = client.get("/api/volume-spike/events")
    assert r.status_code == 200
    assert r.json()["total"] == 1

    r2 = client.get("/api/volume-spike/events?event_type=spike_down")
    assert r2.json()["total"] == 0

    r3 = client.get("/api/volume-spike/events?event_type=spike_up")
    assert r3.json()["total"] == 1


@pytest.mark.integration
def test_volume_spike_events_invalid_date() -> None:
    client, _db = _create_test_app()
    resp = client.get("/api/volume-spike/events?since_date=not-a-date")
    assert resp.status_code == 400
    body = resp.json()
    assert body.get("detail", {}).get("error_type") == "VALIDATION_ERROR"


@pytest.mark.integration
def test_volume_spike_evaluation_summary_empty() -> None:
    client, _db = _create_test_app()
    resp = client.get("/api/volume-spike/evaluation/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_events"] == 0
    assert data["by_horizon"]["1d"]["evaluable_count"] == 0
