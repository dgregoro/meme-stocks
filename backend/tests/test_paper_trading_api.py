from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

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

    # Portfolio summary (unrealized not computed here; just check shape)
    resp = client.get("/api/portfolio")
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["open_positions"] == 1
    assert summary["closed_positions"] == 0

    # Close trade
    resp = client.post(f"/api/trades/{trade_id}/close", json={"exit_price": 12.0})
    assert resp.status_code == 200
    closed = resp.json()
    assert closed["exit_price"] == 12.0

    # Portfolio summary reflects closed position
    resp = client.get("/api/portfolio")
    assert resp.status_code == 200
    summary2 = resp.json()
    assert summary2["open_positions"] == 0
    assert summary2["closed_positions"] == 1


