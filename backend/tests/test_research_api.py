"""Tests for Research API: build-dataset and experiment endpoints."""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.config import get_settings
from backend.app.data.database import Base, engine
from backend.app.main import create_app
from backend.app.services.scheduler_service import SchedulerService


def _make_minimal_dataset(path: str, n_rows: int = 50) -> None:
    """Write minimal CSV with required columns for experiments."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "symbol",
                "trading_day",
                "mention_count",
                "unique_authors",
                "total_upvotes",
                "total_comments",
                "upvote_weighted_mentions",
                "close",
                "volume",
                "y_fwd_return_5",
            ]
        )
        base = date(2026, 1, 1)
        for i in range(n_rows):
            d = base + timedelta(days=i)
            w.writerow(
                [
                    "GME",
                    d.isoformat(),
                    10 + (i % 5),
                    3,
                    50,
                    10,
                    1.5,
                    100.0 + i * 0.5,
                    1000 + i * 10,
                    0.01 * (i % 3 - 1),
                ]
            )


@pytest.fixture
def test_app():
    """Create test FastAPI app with mock scheduler."""
    Base.metadata.create_all(engine)
    mock_scheduler = MagicMock(spec=SchedulerService)
    app = create_app(scheduler_for_testing=mock_scheduler)
    with TestClient(app) as client:
        yield app, mock_scheduler, client
    Base.metadata.drop_all(engine)


@pytest.mark.unit
def test_build_dataset_validation_rejects_invalid_dates(test_app: Any) -> None:
    """Build-dataset returns 400 for invalid date formats."""
    _app, _mock, client = test_app

    r = client.post(
        "/api/research/build-dataset",
        json={"start_day": "invalid", "end_day": "2026-01-15", "horizon": 5},
    )
    assert r.status_code == 400

    r = client.post(
        "/api/research/build-dataset",
        json={"start_day": "2026-01-15", "end_day": "2026-01-01", "horizon": 5},
    )
    assert r.status_code == 400


@pytest.mark.integration
def test_build_dataset_returns_path_and_stats(
    test_app: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Build-dataset runs pipeline and returns path, rows, git_sha."""
    monkeypatch.setenv("RESEARCH_DATASET_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        _app, _mock, client = test_app

        r = client.post(
            "/api/research/build-dataset",
            json={
                "start_day": "2026-01-01",
                "end_day": "2026-01-15",
                "horizon": 5,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert "path" in data
        assert "rows_written" in data
        assert "labels_rows_upserted" in data
        assert "features_rows_upserted" in data
        assert "git_sha" in data
        assert "dataset_version" in data
        assert data["path"].endswith(".csv")
        assert str(tmp_path) in data["path"]
    finally:
        get_settings.cache_clear()


@pytest.mark.unit
def test_directionality_rejects_path_outside_allowed_dir(test_app: Any, tmp_path: Path) -> None:
    """Directionality returns 400 when dataset_path is outside allowed directory."""
    get_settings.cache_clear()
    try:
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        with patch("backend.app.api.research.get_settings") as mock_gs:
            mock_gs.return_value.research_dataset_dir = str(allowed)

            _app, _mock, client = test_app

            # Path outside allowed (e.g. /tmp/other/file.csv)
            outside = tmp_path / "outside" / "dataset.csv"
            outside.parent.mkdir(exist_ok=True)
            outside.write_text("symbol,trading_day\nGME,2026-01-01\n")

            r = client.post(
                "/api/research/experiment/directionality",
                json={"dataset_path": str(outside.resolve()), "k": 5, "h": 1},
            )
            assert r.status_code == 400
            data = r.json().get("detail", r.json())
            assert "message" in data and "must be under" in data["message"].lower()
    finally:
        get_settings.cache_clear()


@pytest.mark.unit
def test_directionality_rejects_nonexistent_file(test_app: Any, tmp_path: Path) -> None:
    """Directionality returns 404 when dataset file does not exist."""
    get_settings.cache_clear()
    try:
        with patch("backend.app.api.research.get_settings") as mock_gs:
            mock_gs.return_value.research_dataset_dir = str(tmp_path)

            _app, _mock, client = test_app

            r = client.post(
                "/api/research/experiment/directionality",
                json={
                    "dataset_path": str(tmp_path / "nonexistent.csv"),
                    "k": 5,
                    "h": 1,
                },
            )
            assert r.status_code == 404
    finally:
        get_settings.cache_clear()


@pytest.mark.unit
def test_directionality_succeeds_with_valid_dataset(test_app: Any, tmp_path: Path) -> None:
    """Directionality returns 200 and correlation stats for valid dataset."""
    get_settings.cache_clear()
    try:
        dataset_path = tmp_path / "dataset.csv"
        _make_minimal_dataset(str(dataset_path), n_rows=40)

        with patch("backend.app.api.research.get_settings") as mock_gs:
            mock_gs.return_value.research_dataset_dir = str(tmp_path)

            _app, _mock, client = test_app

            r = client.post(
                "/api/research/experiment/directionality",
                json={
                    "dataset_path": str(dataset_path.resolve()),
                    "k": 3,
                    "h": 1,
                },
            )
            assert r.status_code == 200
            data = r.json()
            assert "mentions_lead_returns_corr" in data
            assert "mentions_lead_returns_n" in data
            assert "returns_lead_mentions_corr" in data
            assert "returns_lead_mentions_n" in data
    finally:
        get_settings.cache_clear()


@pytest.mark.unit
def test_event_study_succeeds_with_valid_dataset(test_app: Any, tmp_path: Path) -> None:
    """Event study returns 200 and spike/non-spike stats."""
    get_settings.cache_clear()
    try:
        dataset_path = tmp_path / "event_study.csv"
        _make_minimal_dataset(str(dataset_path), n_rows=50)

        with patch("backend.app.api.research.get_settings") as mock_gs:
            mock_gs.return_value.research_dataset_dir = str(tmp_path)

            _app, _mock, client = test_app

            r = client.post(
                "/api/research/experiment/event-study",
                json={
                    "dataset_path": str(dataset_path.resolve()),
                    "window": 10,
                    "threshold": "p95",
                    "horizon": 5,
                },
            )
            assert r.status_code == 200
            data = r.json()
            assert "spike_mean_fwd_return" in data
            assert "spike_n" in data
            assert "non_spike_mean_fwd_return" in data
            assert "non_spike_n" in data
            assert "spread" in data
    finally:
        get_settings.cache_clear()


@pytest.mark.unit
def test_predictiveness_succeeds_with_valid_dataset(test_app: Any, tmp_path: Path) -> None:
    """Predictiveness returns 200 and accuracy/rmse stats."""
    pytest.importorskip("sklearn")
    get_settings.cache_clear()
    try:
        dataset_path = tmp_path / "predictiveness.csv"
        _make_minimal_dataset(str(dataset_path), n_rows=80)

        with patch("backend.app.api.research.get_settings") as mock_gs:
            mock_gs.return_value.research_dataset_dir = str(tmp_path)

            _app, _mock, client = test_app

            r = client.post(
                "/api/research/experiment/predictiveness",
                json={
                    "dataset_path": str(dataset_path.resolve()),
                    "horizon": 5,
                },
            )
            assert r.status_code == 200
            data = r.json()
            assert "baseline_direction_accuracy" in data
            assert "augmented_direction_accuracy" in data
            assert "baseline_ridge_rmse" in data
            assert "augmented_ridge_rmse" in data
            assert "n_train" in data
            assert "n_test" in data
    finally:
        get_settings.cache_clear()
