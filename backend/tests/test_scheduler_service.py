from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from backend.app.data.database import Base, SessionLocal, engine
from backend.app.data.repositories.job_execution_repo import JobExecutionRepository
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.models.job_run_history import JobRunHistory  # noqa: F401 - ensure table created
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
def test_scheduler_service_initialization(mock_yahoo):
    """Test that scheduler service initializes correctly."""
    scheduler = SchedulerService()
    assert scheduler._scheduler is not None
    assert scheduler._settings is not None


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
    if last_run.tzinfo is None:
        last_run = last_run.replace(tzinfo=timezone.utc)
    assert abs((last_run - now).total_seconds()) < 1


@patch("backend.app.services.scheduler_service.YahooFinanceService")
def test_collect_price_data(mock_yahoo_class, db_session, sample_stock):
    """Test price data collection."""
    from backend.app.services.yahoo_service import PriceBar

    mock_yahoo = MagicMock()
    mock_yahoo_class.return_value = mock_yahoo

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

    from backend.app.data.repositories.price_data_repo import PriceDataRepository

    price_repo = PriceDataRepository(db_session)
    prices = price_repo.list_for_stock("GME")
    assert len(prices) == 2


@patch("backend.app.services.scheduler_service.YahooFinanceService")
def test_catch_up_runs_missed_jobs(mock_yahoo_class, db_session, sample_stock):
    """Test that catch-up runs missed jobs."""
    scheduler = SchedulerService()

    price_stats = {"symbols": 0, "rows_inserted": 0, "provider": "yfinance"}
    analysis_stats = {"symbols_processed": 0, "indicators": {}}
    notif_stats = {"symbols_checked": 0, "notifications_generated": 0}

    with (
        patch.object(scheduler, "_collect_price_data", return_value=price_stats) as mock_price,
        patch.object(scheduler, "_run_daily_analysis", return_value=analysis_stats) as mock_analysis,
        patch.object(scheduler, "_check_notifications", return_value=notif_stats) as mock_notif,
    ):
        scheduler._run_catch_up()

        mock_price.assert_called_once()
        mock_analysis.assert_called_once()
        mock_notif.assert_called_once()

        job_repo = JobExecutionRepository(db_session)
        now = datetime.now(timezone.utc)
        job_repo.record_run("price_collection", now)
        job_repo.record_run("daily_analysis", now)
        job_repo.record_run("notification_check", now)
        db_session.commit()

        mock_price.reset_mock()
        mock_analysis.reset_mock()
        mock_notif.reset_mock()

        scheduler._run_catch_up()

        mock_price.assert_not_called()
        mock_analysis.assert_not_called()
        mock_notif.assert_not_called()


@patch("backend.app.services.scheduler_service.JobExecutionRepository")
@patch("backend.app.services.scheduler_service.SessionLocal")
@patch("backend.app.services.scheduler_service.YahooFinanceService")
def test_record_job_failure_swallows_repo_errors(
    mock_yahoo_class,
    mock_session_local,
    mock_job_repo_cls,
):
    """If persisting failure record fails, scheduler still closes DB and logs."""
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    mock_job_repo = MagicMock()
    mock_job_repo.record_run.side_effect = RuntimeError("db down")
    mock_job_repo_cls.return_value = mock_job_repo

    scheduler = SchedulerService()
    scheduler._record_job_failure("test_job", ValueError("boom"))

    mock_db.close.assert_called_once()
    mock_job_repo.record_run.assert_called_once()


@patch("backend.app.services.scheduler_service.YahooFinanceService")
def test_scheduler_start_and_shutdown(mock_yahoo_class):
    """Test scheduler start and shutdown."""
    scheduler = SchedulerService()

    with patch.object(scheduler, "_run_catch_up"), patch.object(scheduler, "_schedule_jobs"):
        scheduler.start()
        assert scheduler._scheduler.running

        scheduler.shutdown()
        assert not scheduler._scheduler.running
