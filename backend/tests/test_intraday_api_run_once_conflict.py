"""Test that POST /api/intraday/run-once returns 409 with structured error when ingestion already running."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app


@pytest.mark.integration
def test_run_once_returns_409_with_error_envelope_when_already_running() -> None:
    """When service raises IngestionAlreadyRunningError, endpoint returns 409 and Appendix C envelope."""
    with patch("backend.app.api.intraday.run_intraday_ingestion") as mock_run:
        mock_run.side_effect = Exception("Intraday ingestion already in progress")
        # Use the exception type the API expects
        from backend.app.utils.errors import IngestionAlreadyRunningError

        mock_run.side_effect = IngestionAlreadyRunningError(
            "Intraday ingestion already in progress",
            owner="scheduler",
            expires_at="2026-03-01T12:30:00+00:00",
        )

        app = create_app(omit_scheduler=True)
        client = TestClient(app)
        response = client.post("/api/intraday/run-once")

    assert response.status_code == 409
    data = response.json()
    # FastAPI puts the exception detail in response.json()["detail"]
    body = data.get("detail", data)
    assert body.get("error") is True
    assert body.get("error_type") == "ConflictError"
    assert "already in progress" in (body.get("message") or "").lower()
    assert "details" in body
    assert body["details"].get("owner") == "scheduler"
    assert body["details"].get("expires_at") == "2026-03-01T12:30:00+00:00"
