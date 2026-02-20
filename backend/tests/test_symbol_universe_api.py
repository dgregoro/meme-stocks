"""Tests for symbol universe API endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.data.database import Base, get_session
from backend.app.main import create_app
from backend.app.utils.errors import ExternalAPIError


@pytest.fixture
def client_and_session() -> tuple[TestClient, Session]:
    """Create test app with overridden session."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    app = create_app(omit_scheduler=True)

    def override_get_session():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app), TestSessionLocal()


def test_refresh_symbol_universe_success(
    client_and_session: tuple[TestClient, Session],
) -> None:
    """Test POST /refresh returns stats on success."""
    client, _ = client_and_session

    with patch("backend.app.api.symbol_universe.SymbolUniverseService") as MockService:
        mock_instance = MagicMock()
        MockService.return_value = mock_instance
        mock_instance.refresh_from_nasdaq.return_value = {
            "inserted": 10,
            "updated": 5,
            "total": 15,
            "errors": [],
        }

        response = client.post("/api/symbol-universe/refresh")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["inserted"] == 10
    assert data["updated"] == 5
    assert data["total"] == 15
    assert data["errors"] == []


def test_refresh_symbol_universe_external_api_error_returns_502(
    client_and_session: tuple[TestClient, Session],
) -> None:
    """Test POST /refresh returns 502 when service raises ExternalAPIError."""
    client, _ = client_and_session

    with patch("backend.app.api.symbol_universe.SymbolUniverseService") as MockService:
        mock_instance = MagicMock()
        MockService.return_value = mock_instance
        mock_instance.refresh_from_nasdaq.side_effect = ExternalAPIError("SEC API unreachable")

        response = client.post("/api/symbol-universe/refresh")

    assert response.status_code == 502
    data = response.json()
    assert data["detail"]["error_type"] == "ExternalAPIError"
    assert "SEC API unreachable" in data["detail"]["message"]


def test_refresh_symbol_universe_generic_error_returns_500(
    client_and_session: tuple[TestClient, Session],
) -> None:
    """Test POST /refresh returns 500 when service raises generic Exception."""
    client, _ = client_and_session

    with patch("backend.app.api.symbol_universe.SymbolUniverseService") as MockService:
        mock_instance = MagicMock()
        MockService.return_value = mock_instance
        mock_instance.refresh_from_nasdaq.side_effect = ValueError("Unexpected parse error")

        response = client.post("/api/symbol-universe/refresh")

    assert response.status_code == 500
    data = response.json()
    assert data["detail"]["error_type"] == "InternalServerError"
    assert "Unexpected parse error" in data["detail"]["message"]


def test_get_universe_stats_success(
    client_and_session: tuple[TestClient, Session],
) -> None:
    """Test GET /stats returns total and active counts."""
    client, _ = client_and_session

    with patch("backend.app.api.symbol_universe.SymbolUniverseService") as MockService:
        mock_instance = MagicMock()
        MockService.return_value = mock_instance
        mock_instance.count.side_effect = [100, 95]  # total, then active_only=True

        response = client.get("/api/symbol-universe/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["total_symbols"] == 100
    assert data["active_symbols"] == 95


def test_get_universe_stats_error_returns_500(
    client_and_session: tuple[TestClient, Session],
) -> None:
    """Test GET /stats returns 500 when service raises Exception."""
    client, _ = client_and_session

    with patch("backend.app.api.symbol_universe.SymbolUniverseService") as MockService:
        mock_instance = MagicMock()
        MockService.return_value = mock_instance
        mock_instance.count.side_effect = RuntimeError("Database connection lost")

        response = client.get("/api/symbol-universe/stats")

    assert response.status_code == 500
    data = response.json()
    assert data["detail"]["error_type"] == "InternalServerError"
    assert "Database connection lost" in data["detail"]["message"]
