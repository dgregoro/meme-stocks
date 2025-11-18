from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.data.database import Base, SessionLocal, engine
from backend.app.main import create_app


@pytest.fixture
def db_session():
    """Create a test database session."""
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_create_stock() -> None:
    """Test creating a new stock."""
    Base.metadata.create_all(engine)
    app = create_app()
    client = TestClient(app)
    
    response = client.post(
        "/api/stocks",
        json={
            "symbol": "GME",
            "name": "GameStop Corp.",
            "sector": "Retail",
            "market_cap": 1000000000.0,
        },
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["symbol"] == "GME"
    assert data["name"] == "GameStop Corp."
    assert data["sector"] == "Retail"
    
    # Verify it was saved
    get_response = client.get("/api/stocks/GME")
    assert get_response.status_code == 200
    assert get_response.json()["symbol"] == "GME"
    
    Base.metadata.drop_all(engine)


def test_create_stock_duplicate() -> None:
    """Test creating a duplicate stock returns 409."""
    Base.metadata.create_all(engine)
    app = create_app()
    client = TestClient(app)
    
    # Create first stock
    client.post(
        "/api/stocks",
        json={"symbol": "GME", "name": "GameStop", "sector": "Retail"},
    )
    
    # Try to create duplicate
    response = client.post(
        "/api/stocks",
        json={"symbol": "GME", "name": "GameStop", "sector": "Retail"},
    )
    
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]["message"]
    
    Base.metadata.drop_all(engine)


def test_create_stock_symbol_uppercase() -> None:
    """Test that stock symbol is converted to uppercase."""
    Base.metadata.create_all(engine)
    app = create_app()
    client = TestClient(app)
    
    response = client.post(
        "/api/stocks",
        json={"symbol": "gme", "name": "GameStop", "sector": "Retail"},
    )
    
    assert response.status_code == 201
    assert response.json()["symbol"] == "GME"  # Should be uppercase
    
    Base.metadata.drop_all(engine)

