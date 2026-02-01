from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import create_app
from backend.app.data.database import Base, get_session
from backend.app.models.stock import Stock


def build_app_with_db():
    engine = create_engine("sqlite:///./test_paper.db", future=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestSessionLocal()

    app = create_app()

    def override_get_session():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app), session


def test_paper_trading_flow() -> None:
    client, db = build_app_with_db()

    # Seed a stock
    db.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    db.commit()

    # Create a trade
    resp = client.post(
        "/api/trades",
        json={"stock_symbol": "GME", "action": "buy", "quantity": 10, "price": 10.0},
    )
    assert resp.status_code == 201
    trade = resp.json()
    trade_id = trade["id"]
    assert trade["stock_symbol"] == "GME"
    assert trade["exit_price"] is None

    # List trades
    resp = client.get("/api/trades")
    assert resp.status_code == 200
    trades = resp.json()
    assert len(trades) == 1

    # Portfolio summary (unrealized not computed here; no closed trades yet)
    resp = client.get("/api/portfolio")
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["open_positions"] == 1
    assert summary["closed_positions"] == 0
    assert summary["win_rate"] is None
    assert summary["average_win"] is None
    assert summary["average_loss"] is None

    # Close trade
    resp = client.post(f"/api/trades/{trade_id}/close", json={"exit_price": 12.0})
    assert resp.status_code == 200
    closed = resp.json()
    assert closed["exit_price"] == 12.0

    # Portfolio summary reflects closed position and win rate
    resp = client.get("/api/portfolio")
    assert resp.status_code == 200
    summary2 = resp.json()
    assert summary2["open_positions"] == 0
    assert summary2["closed_positions"] == 1
    assert summary2["win_rate"] == 1.0  # 1 winning trade
    assert summary2["average_win"] == 20.0  # (12-10)*10
    assert summary2["average_loss"] is None


def test_portfolio_win_rate_mixed_wins_losses() -> None:
    """Test win rate and average win/loss with mixed outcomes."""
    client, db = build_app_with_db()
    db.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    db.commit()

    # Create and close 3 trades: 2 wins, 1 loss
    r1 = client.post("/api/trades", json={"stock_symbol": "GME", "action": "buy", "quantity": 10, "price": 10.0})
    r2 = client.post("/api/trades", json={"stock_symbol": "GME", "action": "buy", "quantity": 5, "price": 20.0})
    r3 = client.post("/api/trades", json={"stock_symbol": "GME", "action": "buy", "quantity": 10, "price": 15.0})
    for r in [r1, r2, r3]:
        assert r.status_code == 201
    t1_id, t2_id, t3_id = r1.json()["id"], r2.json()["id"], r3.json()["id"]

    client.post(f"/api/trades/{t1_id}/close", json={"exit_price": 12.0})  # +20
    client.post(f"/api/trades/{t2_id}/close", json={"exit_price": 18.0})  # -10
    client.post(f"/api/trades/{t3_id}/close", json={"exit_price": 17.0})  # +20

    resp = client.get("/api/portfolio")
    assert resp.status_code == 200
    s = resp.json()
    assert s["win_rate"] == pytest.approx(2 / 3, rel=1e-3)  # 2 wins of 3
    assert s["average_win"] == 20.0  # (20+20)/2
    assert s["average_loss"] == -10.0  # single loss
