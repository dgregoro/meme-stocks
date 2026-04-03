from __future__ import annotations


def test_create_stock(isolated_omit_scheduler_client):
    """Test creating a new stock."""
    client, _MainSession = isolated_omit_scheduler_client

    sym = "TST1"
    response = client.post(
        "/api/stocks",
        json={
            "symbol": sym,
            "name": "Test Corp.",
            "sector": "Retail",
            "market_cap": 1000000000.0,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["symbol"] == sym
    assert data["name"] == "Test Corp."
    assert data["sector"] == "Retail"

    get_response = client.get(f"/api/stocks/{sym}")
    assert get_response.status_code == 200
    assert get_response.json()["symbol"] == sym


def test_create_stock_duplicate(isolated_omit_scheduler_client):
    """Test creating a duplicate stock returns 409."""
    client, _MainSession = isolated_omit_scheduler_client

    client.post(
        "/api/stocks",
        json={"symbol": "GME", "name": "GameStop", "sector": "Retail"},
    )

    response = client.post(
        "/api/stocks",
        json={"symbol": "GME", "name": "GameStop", "sector": "Retail"},
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]["message"]


def test_create_stock_symbol_uppercase(isolated_omit_scheduler_client):
    """Test that stock symbol is converted to uppercase."""
    client, _MainSession = isolated_omit_scheduler_client

    response = client.post(
        "/api/stocks",
        json={"symbol": "gme", "name": "GameStop", "sector": "Retail"},
    )

    assert response.status_code == 201
    assert response.json()["symbol"] == "GME"
