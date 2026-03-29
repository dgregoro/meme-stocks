from __future__ import annotations

from collections.abc import Generator
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from backend.app.data.database import Base, get_session
from backend.app.main import create_app
from backend.app.models.job_run_history import JobRunHistory
from backend.app.models.price_data import PriceData
from backend.app.models.stock import Stock
from backend.app.services import status_service as status_service_module


def _build_test_app_with_db() -> tuple[TestClient, Session]:
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

    def override_get_session() -> Generator[Session, None, None]:
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app), session


def test_get_collection_status_counters_and_health(monkeypatch: pytest.MonkeyPatch) -> None:
    """Status endpoint returns expected structure and basic counter/health correctness."""
    client, db = _build_test_app_with_db()

    fixed_now = datetime(2026, 3, 2, 12, 0, 0, tzinfo=timezone.utc)

    class FixedDateTime(datetime):  # type: ignore[misc]
        @classmethod
        def now(cls, tz: timezone | None = None) -> datetime:  # type: ignore[override]
            if tz is None:
                return fixed_now
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(status_service_module, "datetime", FixedDateTime)

    stock = Stock(symbol="GME", name="GameStop", sector=None, market_cap=None)
    db.add(stock)

    price = PriceData(
        stock_symbol="GME",
        date=fixed_now.date(),
        open=10.0,
        high=12.0,
        low=9.5,
        close=11.0,
        volume=1000,
    )
    db.add(price)
    db.commit()

    resp = client.get("/api/status/collection")
    assert resp.status_code == 200
    body = resp.json()

    assert "server_time_utc" in body
    assert "market_time_local" in body
    assert isinstance(body.get("jobs"), list)
    assert "reddit" not in body

    prices = body.get("prices")
    assert isinstance(prices, dict)
    assert prices["newest_price_date"].startswith(fixed_now.date().isoformat())
    assert prices["price_rows_last_7d"] == 1
    assert prices["price_rows_last_30d"] == 1

    health = body.get("health")
    assert isinstance(health, dict)
    assert health["prices"] in {"ok", "stale", "empty"}
    assert health["jobs"] in {"ok", "warning"}
    assert "thresholds" in body
    assert body["thresholds"]["prices_stale_after_days"] == 2


def test_collection_status_with_job_history(monkeypatch: pytest.MonkeyPatch) -> None:
    """Collection status reflects job runs in history."""
    client, db = _build_test_app_with_db()

    fixed_now = datetime(2026, 3, 2, 12, 0, 0, tzinfo=timezone.utc)

    class FixedDateTime(datetime):  # type: ignore[misc]
        @classmethod
        def now(cls, tz: timezone | None = None) -> datetime:  # type: ignore[override]
            if tz is None:
                return fixed_now
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(status_service_module, "datetime", FixedDateTime)

    t_run = datetime(2026, 3, 2, 11, 0, 0, tzinfo=timezone.utc)
    db.add(
        JobRunHistory(
            job_name="price_collection",
            run_at=t_run,
            success=True,
            error_message=None,
        )
    )

    stock = Stock(symbol="GME", name="GameStop", sector=None, market_cap=None)
    db.add(stock)
    db.add(
        PriceData(
            stock_symbol="GME",
            date=fixed_now.date(),
            open=10.0,
            high=12.0,
            low=9.5,
            close=11.0,
            volume=1000,
        )
    )
    db.commit()

    resp = client.get("/api/status/collection")
    assert resp.status_code == 200
    body = resp.json()
    assert body["health"]["jobs"] in {"ok", "warning"}


def test_stale_symbols_stale_price(monkeypatch: pytest.MonkeyPatch) -> None:
    """get /symbols/stale marks symbols with old price data."""
    client, db = _build_test_app_with_db()

    fixed_now = datetime(2026, 3, 2, 12, 0, 0, tzinfo=timezone.utc)

    class FixedDateTime(datetime):  # type: ignore[misc]
        @classmethod
        def now(cls, tz: timezone | None = None) -> datetime:  # type: ignore[override]
            if tz is None:
                return fixed_now
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(status_service_module, "datetime", FixedDateTime)

    stock = Stock(symbol="GME", name="GameStop", sector=None, market_cap=None)
    db.add(stock)

    old_day = date(2026, 2, 20)
    db.add(
        PriceData(
            stock_symbol="GME",
            date=old_day,
            open=10.0,
            high=12.0,
            low=9.5,
            close=11.0,
            volume=1000,
        )
    )
    db.commit()

    resp = client.get("/api/status/symbols/stale?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    symbols = [s["symbol"] for s in data]
    assert "GME" in symbols
    gme = next(s for s in data if s["symbol"] == "GME")
    assert "price_stale" in gme["stale_reasons"]


def test_status_jobs_runs_empty_returns_empty_list() -> None:
    """GET /api/status/jobs/runs returns [] when no runs exist, no 500."""
    client, _ = _build_test_app_with_db()
    resp = client.get("/api/status/jobs/runs")
    assert resp.status_code == 200
    assert resp.json() == []


def test_status_jobs_runs_returns_history_with_datetimes_and_duration() -> None:
    """GET /api/status/jobs/runs returns runs with UTC-aware finished_at_utc, started_at, duration."""
    client, db = _build_test_app_with_db()

    t0 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    started = datetime(2026, 3, 1, 9, 59, 55, tzinfo=timezone.utc)
    db.add(
        JobRunHistory(
            job_name="price_collection",
            run_at=t0,
            started_at=started,
            duration_seconds=5.0,
            success=True,
            error_message=None,
        )
    )
    db.commit()

    resp = client.get("/api/status/jobs/runs?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["job_name"] == "price_collection"
    assert data[0]["success"] is True
    assert data[0]["duration_seconds"] == 5.0
    assert "finished_at_utc" in data[0]
    assert "started_at_utc" in data[0]
    fin = data[0]["finished_at_utc"]
    assert fin is not None and ("Z" in str(fin) or "+00:00" in str(fin))


def test_status_jobs_job_name_runs_returns_started_finished_duration() -> None:
    """GET /api/status/jobs/{job_name}/runs returns started_at_utc, finished_at_utc, duration."""
    client, db = _build_test_app_with_db()

    t0 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    started = datetime(2026, 3, 1, 9, 59, 55, tzinfo=timezone.utc)
    db.add(
        JobRunHistory(
            job_name="price_collection",
            run_at=t0,
            started_at=started,
            duration_seconds=5.0,
            success=True,
            error_message=None,
        )
    )
    db.commit()

    resp = client.get("/api/status/jobs/price_collection/runs?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["job_name"] == "price_collection"
    assert data[0]["started_at_utc"] is not None
    assert data[0]["finished_at_utc"] is not None
    assert data[0]["duration_seconds"] == 5.0


def test_status_collection_includes_last_success_utc() -> None:
    """Collection status jobs include last_success_utc when available."""
    client, db = _build_test_app_with_db()

    t0 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    db.add(JobRunHistory(job_name="price_collection", run_at=t0, success=True, error_message=None))
    db.commit()

    resp = client.get("/api/status/collection")
    assert resp.status_code == 200
    jobs = resp.json().get("jobs", [])
    price_job = next((j for j in jobs if j["job_id"] == "price_collection"), None)
    assert price_job is not None
    assert "last_success_utc" in price_job


def test_job_runs_endpoint_returns_metrics_json_parsed() -> None:
    """GET /api/status/jobs/runs returns summary and metrics (parsed from metrics_json)."""
    client, db = _build_test_app_with_db()

    t0 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    db.add(
        JobRunHistory(
            job_name="price_collection",
            run_at=t0,
            started_at=t0,
            duration_seconds=5.0,
            success=True,
            error_message=None,
            summary="prices: 42 rows inserted for 3 symbols",
            metrics_json='{"rows_inserted":42,"symbols":3}',
        )
    )
    db.commit()

    resp = client.get("/api/status/jobs/runs?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    run = data[0]
    assert run["summary"] == "prices: 42 rows inserted for 3 symbols"
    assert run["metrics"] == {"rows_inserted": 42, "symbols": 3}


def test_job_runs_endpoint_handles_missing_metrics_gracefully() -> None:
    """Runs with no metrics_json still display; metrics is None, summary preserved."""
    client, db = _build_test_app_with_db()

    t0 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    db.add(
        JobRunHistory(
            job_name="notification_check",
            run_at=t0,
            success=True,
            error_message=None,
            summary="notifications: 0 generated for 2 symbols",
            metrics_json=None,
        )
    )
    db.commit()

    resp = client.get("/api/status/jobs/runs?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["summary"] == "notifications: 0 generated for 2 symbols"
    assert data[0]["metrics"] is None


def test_status_jobs_runs_returns_500_on_data_access_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/status/jobs/runs returns 500 with error detail when repo raises DataAccessError."""
    from backend.app.utils.errors import DataAccessError

    def _raise_data_access_error(*args, **kwargs):
        raise DataAccessError("simulated repo failure")

    monkeypatch.setattr(
        "backend.app.data.repositories.job_execution_repo.JobExecutionRepository.list_recent_runs",
        _raise_data_access_error,
    )

    client, _ = _build_test_app_with_db()
    resp = client.get("/api/status/jobs/runs?limit=10")
    assert resp.status_code == 500
    body = resp.json()
    assert "detail" in body
    detail = body["detail"]
    assert "DataAccessError" in str(detail) or "simulated" in str(detail)
