from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from backend.app.data.database import Base, SessionLocal, engine
from backend.app.data.repositories.job_execution_repo import JobExecutionRepository
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.models.job_run_history import JobRunHistory  # noqa: F401 - ensure table created
from backend.app.models.reddit_symbol_mention import RedditSymbolMention  # noqa: F401 - Stock relationship
from backend.app.models.stock import Stock
from backend.app.services.scheduler_service import SchedulerService


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


@pytest.fixture
def sample_stock(db_session):
    """Create a sample stock for testing."""
    stock = Stock(
        symbol="GME",
        name="GameStop Corp.",
        sector="Retail",
        market_cap=1000000000.0,
    )
    repo = StockRepository(db_session)
    repo.add(stock)
    db_session.commit()
    return stock


@patch("backend.app.services.scheduler_service.YahooFinanceService")
@patch("backend.app.services.scheduler_service.RedditService")
def test_scheduler_service_initialization(mock_reddit, mock_yahoo):
    """Test that scheduler service initializes correctly."""
    scheduler = SchedulerService()
    assert scheduler._scheduler is not None
    assert scheduler._settings is not None


@patch("backend.app.services.scheduler_service.get_settings")
@patch("backend.app.services.scheduler_service.YahooFinanceService")
def test_collect_reddit_data_skipped_when_credentials_missing(mock_yahoo, mock_get_settings, db_session):
    """When Reddit credentials are empty, Reddit collection returns zero stats without calling API."""
    from backend.app.services.job_metrics import (
        REDDIT_POSTS_FETCHED,
        REDDIT_POSTS_INSERTED,
        REDDIT_SYMBOLS_MENTIONED,
        REDDIT_STOCKS_CREATED,
    )

    mock_settings = MagicMock()
    mock_settings.reddit_client_id = ""
    mock_settings.reddit_client_secret = ""
    mock_settings.reddit_subreddits = "wallstreetbets"
    mock_get_settings.return_value = mock_settings

    scheduler = SchedulerService()
    assert scheduler._reddit_service is None

    stats = scheduler._collect_reddit_data(db_session)

    assert stats[REDDIT_POSTS_FETCHED] == 0
    assert stats[REDDIT_POSTS_INSERTED] == 0
    assert stats[REDDIT_SYMBOLS_MENTIONED] == 0
    assert stats[REDDIT_STOCKS_CREATED] == 0


def test_job_execution_repository_get_last_run_none(db_session):
    """Test getting last run time when job has never run."""
    repo = JobExecutionRepository(db_session)
    assert repo.get_last_run("test_job") is None


def test_job_execution_repository_record_and_get_run(db_session):
    """Test recording and retrieving job execution."""
    repo = JobExecutionRepository(db_session)
    now = datetime.now(timezone.utc)

    repo.record_run("test_job", now)
    db_session.commit()

    last_run = repo.get_last_run("test_job")
    assert last_run is not None
    # Ensure both are timezone-aware for comparison
    if last_run.tzinfo is None:
        last_run = last_run.replace(tzinfo=timezone.utc)
    assert abs((last_run - now).total_seconds()) < 1


@patch("backend.app.services.scheduler_service.RedditService")
@patch("backend.app.services.scheduler_service.YahooFinanceService")
def test_collect_reddit_data_with_tickers(mock_yahoo, mock_reddit_class, db_session, sample_stock):
    """Test Reddit data collection with auto-discovery of stocks."""
    from backend.app.data.repositories.symbol_universe_repo import SymbolUniverseRepository
    from backend.app.models.symbol_universe import SymbolUniverse

    # Seed symbol universe so extract_tickers only returns GME and AAPL (reduces false positives)
    universe_repo = SymbolUniverseRepository(db_session)
    for sym in ("GME", "AAPL"):
        universe_repo.add(SymbolUniverse(symbol=sym, is_active=True))
    db_session.commit()
    from backend.app.utils.ticker_extractor import clear_symbol_universe_cache

    clear_symbol_universe_cache()

    # Mock Reddit service
    mock_reddit = MagicMock()
    mock_reddit_class.return_value = mock_reddit

    from backend.app.services.reddit_service import RedditPostData

    mock_posts = [
        RedditPostData(
            id="post1",
            stock_symbol="",
            subreddit="wallstreetbets",
            title="GME is going up! $GME",
            author="user1",
            upvotes=100,
            comments=50,
            url="https://reddit.com/r/wallstreetbets/post1",
            posted_at=datetime.now(timezone.utc),
            collected_at=datetime.now(timezone.utc),
        ),
        RedditPostData(
            id="post2",
            stock_symbol="",
            subreddit="stocks",
            title="Just bought some AAPL shares",
            author="user2",
            upvotes=10,
            comments=5,
            url="https://reddit.com/r/stocks/post2",
            posted_at=datetime.now(timezone.utc),
            collected_at=datetime.now(timezone.utc),
        ),
    ]
    mock_reddit.fetch_recent_posts.return_value = mock_posts

    scheduler = SchedulerService()
    scheduler._reddit_service = mock_reddit

    stats = scheduler._collect_reddit_data(db_session)
    db_session.commit()

    from backend.app.services.job_metrics import (
        REDDIT_POSTS_FETCHED,
        REDDIT_POSTS_INSERTED,
        REDDIT_SYMBOLS_MENTIONED,
    )

    assert stats[REDDIT_POSTS_FETCHED] == 2
    assert stats[REDDIT_SYMBOLS_MENTIONED] == 2
    assert stats[REDDIT_POSTS_INSERTED] >= 2
    assert stats["stocks_created"] == 1  # AAPL auto-created (GME already exists)

    from backend.app.data.repositories.reddit_post_repo import RedditPostRepository
    from backend.app.data.repositories.stock_repo import StockRepository

    reddit_repo = RedditPostRepository(db_session)
    stock_repo = StockRepository(db_session)

    posts = reddit_repo.list_for_stock("GME")
    assert len(posts) == 1
    assert posts[0].id == "post1"

    aapl_stock = stock_repo.get("AAPL")
    assert aapl_stock is not None
    assert aapl_stock.name == "AAPL (auto-discovered)"

    aapl_posts = reddit_repo.list_for_stock("AAPL")
    assert len(aapl_posts) == 1
    assert aapl_posts[0].id == "post2"


@patch("backend.app.services.scheduler_service.YahooFinanceService")
@patch("backend.app.services.scheduler_service.RedditService")
def test_collect_price_data(mock_yahoo_class, mock_reddit_class, db_session, sample_stock):
    """Test price data collection."""
    from backend.app.services.yahoo_service import PriceBar

    mock_yahoo = MagicMock()
    mock_yahoo_class.return_value = mock_yahoo

    # Mock price bars
    today = date.today()
    mock_bars = [
        PriceBar(
            stock_symbol="GME",
            date=today - timedelta(days=1),
            open=10.0,
            high=12.0,
            low=9.0,
            close=11.0,
            volume=1000000,
            source_timestamp=datetime.now(timezone.utc),
        ),
        PriceBar(
            stock_symbol="GME",
            date=today,
            open=11.0,
            high=13.0,
            low=10.0,
            close=12.0,
            volume=1500000,
            source_timestamp=datetime.now(timezone.utc),
        ),
    ]
    mock_yahoo.fetch_historical_prices.return_value = mock_bars

    scheduler = SchedulerService()
    scheduler._yahoo_service = mock_yahoo

    scheduler._collect_price_data(db_session)
    db_session.commit()

    # Check that price data was saved
    from backend.app.data.repositories.price_data_repo import PriceDataRepository

    price_repo = PriceDataRepository(db_session)
    prices = price_repo.list_for_stock("GME")
    assert len(prices) == 2


@patch("backend.app.services.scheduler_service.YahooFinanceService")
@patch("backend.app.services.scheduler_service.RedditService")
def test_catch_up_runs_missed_jobs(mock_yahoo_class, mock_reddit_class, db_session, sample_stock):
    """Test that catch-up runs missed jobs."""
    scheduler = SchedulerService()

    # Mock the collection methods; use canonical keys from job_metrics
    reddit_stats = {
        "posts_fetched": 0,
        "posts_inserted": 0,
        "symbols_mentioned": 0,
        "stocks_created": 0,
    }
    price_stats = {"symbols": 0, "rows_inserted": 0, "provider": "yfinance"}
    analysis_stats = {"symbols_processed": 0, "indicators": {}}
    notif_stats = {"symbols_checked": 0, "notifications_generated": 0}

    with (
        patch.object(scheduler, "_collect_reddit_data", return_value=reddit_stats) as mock_reddit,
        patch.object(scheduler, "_collect_price_data", return_value=price_stats) as mock_price,
        patch.object(scheduler, "_run_daily_analysis", return_value=analysis_stats) as mock_analysis,
        patch.object(scheduler, "_check_notifications", return_value=notif_stats) as mock_notif,
        patch.object(scheduler, "_run_reddit_daily_features", return_value={"rows_upserted": 0, "symbols_seen": 0}),
    ):

        # First run - no previous executions
        scheduler._run_catch_up()

        # All jobs should have been called
        mock_reddit.assert_called_once()
        mock_price.assert_called_once()
        mock_analysis.assert_called_once()
        mock_notif.assert_called_once()

        # Record runs
        job_repo = JobExecutionRepository(db_session)
        now = datetime.now(timezone.utc)
        job_repo.record_run("reddit_collection", now)
        job_repo.record_run("price_collection", now)
        job_repo.record_run("daily_analysis", now)
        job_repo.record_run("notification_check", now)
        db_session.commit()

        # Reset mocks
        mock_reddit.reset_mock()
        mock_price.reset_mock()
        mock_analysis.reset_mock()
        mock_notif.reset_mock()

        # Second run immediately - should not trigger catch-up (too recent)
        scheduler._run_catch_up()

        # Jobs should not be called again (too recent)
        mock_reddit.assert_not_called()
        mock_price.assert_not_called()
        mock_analysis.assert_not_called()
        mock_notif.assert_not_called()


@patch("backend.app.services.scheduler_service.YahooFinanceService")
@patch("backend.app.services.scheduler_service.RedditService")
@patch("backend.app.services.scheduler_service.SessionLocal")
def test_collect_reddit_data_job_calls_record_run_with_metrics(
    mock_session_local, mock_reddit_class, mock_yahoo_class, db_session
):
    """Reddit collection job wrapper calls record_run with metrics including posts_inserted."""
    mock_session_local.return_value = db_session

    scheduler = SchedulerService()
    mock_stats = {
        "posts_fetched": 100,
        "posts_inserted": 42,
        "symbols_mentioned": 88,
        "stocks_created": 2,
    }

    with patch.object(scheduler, "_collect_reddit_data", return_value=mock_stats):
        scheduler._collect_reddit_data_job()

    # Verify record_run was called with summary and metrics
    repo = JobExecutionRepository(db_session)
    runs = repo.list_recent_runs(job_name="reddit_collection", limit=1)
    assert len(runs) == 1
    assert runs[0].summary == "reddit: inserted 42 posts (100 fetched), symbols=88"
    assert runs[0].metrics_json is not None
    import json

    parsed = json.loads(runs[0].metrics_json)
    assert parsed["posts_inserted"] == 42
    assert parsed["posts_fetched"] == 100
    assert parsed["symbols_mentioned"] == 88


@patch("backend.app.services.scheduler_service.YahooFinanceService")
@patch("backend.app.services.scheduler_service.RedditService")
def test_scheduler_start_and_shutdown(mock_yahoo_class, mock_reddit_class):
    """Test scheduler start and shutdown."""
    scheduler = SchedulerService()

    # Mock catch-up and scheduling to avoid actual job execution
    with patch.object(scheduler, "_run_catch_up"), patch.object(scheduler, "_schedule_jobs"):

        scheduler.start()
        assert scheduler._scheduler.running

        scheduler.shutdown()
        assert not scheduler._scheduler.running
