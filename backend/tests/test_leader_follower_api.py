"""Tests for leader-follower API."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import create_app
from backend.app.data.database import Base, get_session
from backend.app.models.leader_follower_signal import LeaderFollowerSignal
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


@pytest.mark.unit
def test_leader_follower_api_list_signals() -> None:
    """GET /api/leader-follower/signals returns list; query params limit, since_date, leader, group work."""
    client, db = _create_test_app()

    db.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    db.add(Stock(symbol="AMC", name="AMC", sector="Entertainment", market_cap=None))
    db.commit()

    signal = LeaderFollowerSignal(
        leader_symbol="GME",
        follower_symbol="AMC",
        group_id="meme",
        signal_date=date(2026, 3, 18),
        strength_score=0.72,
        leader_return_pct=8.5,
        leader_volume_ratio=2.1,
    )
    db.add(signal)
    db.commit()

    resp = client.get("/api/leader-follower/signals")
    assert resp.status_code == 200
    data = resp.json()
    assert "signals" in data
    assert len(data["signals"]) == 1
    s = data["signals"][0]
    assert s["leader_symbol"] == "GME"
    assert s["follower_symbol"] == "AMC"
    assert s["group_id"] == "meme"
    assert s["strength_score"] == 0.72
    assert s["leader_return_pct"] == 8.5

    resp2 = client.get("/api/leader-follower/signals?limit=10")
    assert resp2.status_code == 200
    assert len(resp2.json()["signals"]) == 1

    resp3 = client.get("/api/leader-follower/signals?leader=GME")
    assert resp3.status_code == 200
    assert len(resp3.json()["signals"]) == 1

    resp4 = client.get("/api/leader-follower/signals?leader=XXX")
    assert resp4.status_code == 200
    assert len(resp4.json()["signals"]) == 0

    resp5 = client.get("/api/leader-follower/signals?group=meme")
    assert resp5.status_code == 200
    assert len(resp5.json()["signals"]) == 1

    resp6 = client.get("/api/leader-follower/signals?since_date=2026-03-17")
    assert resp6.status_code == 200
    assert len(resp6.json()["signals"]) == 1
