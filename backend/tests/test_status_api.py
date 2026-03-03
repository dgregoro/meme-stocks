from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.data.database import Base, get_session
from backend.app.main import create_app
from backend.app.models.job_run_history import JobRunHistory
from backend.app.models.price_data import PriceData
from backend.app.models.reddit_daily_feature import RedditDailyFeature
from backend.app.models.reddit_post import RedditPost
from backend.app.models.reddit_symbol_mention import RedditSymbolMention
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
    app = create_app()

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

    # Fix \"now\" inside status_service so time windows are deterministic.
    fixed_now = datetime(2026, 3, 2, 12, 0, 0, tzinfo=timezone.utc)

    class FixedDateTime(datetime):  # type: ignore[misc]
        @classmethod
        def now(cls, tz: timezone | None = None) -> datetime:  # type: ignore[override]
            if tz is None:
                return fixed_now
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(status_service_module, "datetime", FixedDateTime)

    # Seed minimal data so counters are non-zero and types exercised.
    stock = Stock(symbol="GME", name="GameStop", sector=None, market_cap=None)
    db.add(stock)

    post = RedditPost(
        id="post1",
        subreddit="wallstreetbets",
        title="GME to the moon",
        author="u1",
        upvotes=10,
        comments=2,
        url="https://reddit.com/...",
        posted_at=fixed_now - timedelta(minutes=30),
        collected_at=fixed_now - timedelta(minutes=30),
    )
    db.add(post)
    db.add(RedditSymbolMention(post_id="post1", symbol="GME"))

    # Older Reddit post outside 1h window but inside 24h.
    older_post = RedditPost(
        id="post_old",
        subreddit="wallstreetbets",
        title="GME earlier",
        author="u2",
        upvotes=3,
        comments=1,
        url="https://reddit.com/...",
        posted_at=fixed_now - timedelta(hours=2),
        collected_at=fixed_now - timedelta(hours=2),
    )
    db.add(older_post)
    db.add(RedditSymbolMention(post_id="post_old", symbol="GME"))

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

    feature = RedditDailyFeature(
        symbol="GME",
        trading_day=fixed_now.date(),
        mention_count=1,
        unique_authors=1,
        total_upvotes=10,
        total_comments=2,
        upvote_weighted_mentions=1.0,
    )
    db.add(feature)
    db.commit()

    resp = client.get("/api/status/collection")
    assert resp.status_code == 200
    body = resp.json()

    assert "server_time_utc" in body
    assert "market_time_local" in body
    assert isinstance(body.get("jobs"), list)

    reddit = body.get("reddit")
    assert isinstance(reddit, dict)
    assert reddit["posts_last_1h"] == 1
    assert reddit["posts_last_24h"] == 2
    assert reddit["mentions_last_1h"] == 1
    assert reddit["mentions_last_24h"] == 2

    prices = body.get("prices")
    assert isinstance(prices, dict)
    assert prices["newest_price_date"].startswith(fixed_now.date().isoformat())
    assert prices["price_rows_last_7d"] == 1
    assert prices["price_rows_last_30d"] == 1

    daily = body.get("daily_features")
    assert isinstance(daily, dict)
    assert daily["newest_trading_day"].startswith(fixed_now.date().isoformat())
    assert daily["rows_last_7d"] == 1
    assert daily["rows_last_30d"] == 1

    health = body.get("health")
    assert isinstance(health, dict)
    assert health["reddit"] in {"ok", "stale", "empty"}
    assert health["prices"] in {"ok", "stale", "empty"}
    assert health["daily_features"] in {"ok", "stale", "empty"}
    assert health["jobs"] in {"ok", "warning"}


def test_collection_status_with_naive_datetimes_from_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """Status endpoints handle naive datetimes from DB (e.g. SQLite) without TypeError."""
    client, db = _build_test_app_with_db()

    fixed_now = datetime(2026, 3, 2, 12, 0, 0, tzinfo=timezone.utc)

    class FixedDateTime(datetime):  # type: ignore[misc]
        @classmethod
        def now(cls, tz: timezone | None = None) -> datetime:  # type: ignore[override]
            if tz is None:
                return fixed_now
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(status_service_module, "datetime", FixedDateTime)

    # Insert JobExecution with naive datetime (SQLite returns naive for non-TZ strings).
    db.execute(
        text(
            "INSERT INTO job_executions (job_name, last_run_at, created_at, updated_at) "
            "VALUES ('reddit_collection', '2026-03-02 11:00:00', '2026-03-02 11:00:00', '2026-03-02 11:00:00')"
        )
    )

    stock = Stock(symbol="GME", name="GameStop", sector=None, market_cap=None)
    db.add(stock)

    # RedditPost with naive collected_at (30 min before fixed_now when treated as UTC).
    naiv_30m_ago = datetime(2026, 3, 2, 11, 30, 0)
    post = RedditPost(
        id="post1",
        subreddit="wallstreetbets",
        title="GME",
        author="u1",
        upvotes=10,
        comments=2,
        url="https://reddit.com/...",
        posted_at=naiv_30m_ago,
        collected_at=naiv_30m_ago,
    )
    db.add(post)
    db.add(RedditSymbolMention(post_id="post1", symbol="GME"))
    db.commit()

    resp = client.get("/api/status/collection")
    assert resp.status_code == 200
    body = resp.json()
    assert "health" in body
    assert body["health"]["reddit"] == "ok"  # 30 min ago < 120 min threshold (naive treated as UTC)
    assert body["health"]["jobs"] in {"ok", "warning"}


def test_stale_symbols_with_naive_datetimes(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_stale_symbols handles naive collected_at from DB without TypeError."""
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

    # Post with naive collected_at 3 hours ago (stale per 120 min threshold).
    naiv_3h_ago = datetime(2026, 3, 2, 9, 0, 0)
    post = RedditPost(
        id="post1",
        subreddit="wallstreetbets",
        title="GME",
        author="u1",
        upvotes=10,
        comments=2,
        url="https://reddit.com/...",
        posted_at=naiv_3h_ago,
        collected_at=naiv_3h_ago,
    )
    db.add(post)
    db.add(RedditSymbolMention(post_id="post1", symbol="GME"))
    db.commit()

    resp = client.get("/api/status/symbols/stale?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    symbols = [s["symbol"] for s in data]
    assert "GME" in symbols
    gme = next(s for s in data if s["symbol"] == "GME")
    assert "reddit_stale" in gme["stale_reasons"]


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
            job_name="reddit_collection",
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
    assert data[0]["job_name"] == "reddit_collection"
    assert data[0]["success"] is True
    assert data[0]["duration_seconds"] == 5.0
    assert "finished_at_utc" in data[0]
    assert "started_at_utc" in data[0]
    # ISO8601 should include timezone (Z or +00:00)
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
    db.add(JobRunHistory(job_name="reddit_collection", run_at=t0, success=True, error_message=None))
    db.commit()

    resp = client.get("/api/status/collection")
    assert resp.status_code == 200
    jobs = resp.json().get("jobs", [])
    reddit_job = next((j for j in jobs if j["job_id"] == "reddit_collection"), None)
    assert reddit_job is not None
    assert "last_success_utc" in reddit_job


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
