from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.data.database import SessionLocal
from backend.app.data.repositories.job_execution_repo import JobExecutionRepository
from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.data.repositories.reddit_post_repo import RedditPostRepository
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.models.price_data import PriceData
from backend.app.models.reddit_post import RedditPost
from backend.app.services.analysis_service import run_daily_analysis
from backend.app.services.notification_service import generate_notifications_for_stock
from backend.app.services.reddit_service import RedditService
from backend.app.services.yahoo_service import YahooFinanceService
from backend.app.utils.errors import DataAccessError, ExternalAPIError
from backend.app.utils.ticker_extractor import extract_tickers

logger = logging.getLogger(__name__)


class SchedulerService:
    """Manages scheduled background jobs with catch-up support.

    On startup, checks for missed jobs and runs them. Then schedules periodic
    jobs going forward. All errors are logged but do not stop the scheduler.
    """

    def __init__(self) -> None:
        self._scheduler = BackgroundScheduler()
        self._settings = get_settings()
        self._reddit_service = RedditService()
        self._yahoo_service = YahooFinanceService()

    def start(self) -> None:
        """Start the scheduler and run catch-up if enabled."""
        if self._settings.enable_catch_up:
            logger.info("Running catch-up for missed jobs...")
            self._run_catch_up()

        # Schedule periodic jobs
        self._schedule_jobs()
        self._scheduler.start()
        logger.info("Scheduler started")

    def shutdown(self) -> None:
        """Shutdown the scheduler gracefully."""
        self._scheduler.shutdown()
        logger.info("Scheduler stopped")

    def _run_catch_up(self) -> None:
        """Check for missed jobs and run them."""
        db = SessionLocal()
        try:
            job_repo = JobExecutionRepository(db)
            now = datetime.now(timezone.utc)

            def ensure_timezone_aware(dt: datetime | None) -> datetime | None:
                """Ensure datetime is timezone-aware, converting naive to UTC if needed."""
                if dt is None:
                    return None
                if dt.tzinfo is None:
                    return dt.replace(tzinfo=timezone.utc)
                return dt

            # Check Reddit collection
            last_reddit = ensure_timezone_aware(job_repo.get_last_run("reddit_collection"))
            if last_reddit is None or (now - last_reddit).total_seconds() > 3600:
                logger.info("Catching up on Reddit collection...")
                self._collect_reddit_data(db)
                job_repo.record_run("reddit_collection", now)
                db.commit()

            # Check price collection
            last_price = ensure_timezone_aware(job_repo.get_last_run("price_collection"))
            if last_price is None or (now - last_price).total_seconds() > 900:
                logger.info("Catching up on price collection...")
                self._collect_price_data(db)
                job_repo.record_run("price_collection", now)
                db.commit()

            # Check daily analysis (run if we haven't run one today)
            last_analysis = ensure_timezone_aware(job_repo.get_last_run("daily_analysis"))
            today_start = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            if last_analysis is None or last_analysis < today_start:
                logger.info("Catching up on daily analysis...")
                self._run_daily_analysis(db)
                job_repo.record_run("daily_analysis", now)
                db.commit()

            # Check notifications
            last_notif = ensure_timezone_aware(job_repo.get_last_run("notification_check"))
            if last_notif is None or (now - last_notif).total_seconds() > 1800:
                logger.info("Catching up on notification checks...")
                self._check_notifications(db)
                job_repo.record_run("notification_check", now)
                db.commit()

        except Exception as exc:
            logger.error(f"Error during catch-up: {exc}", exc_info=True)
            db.rollback()
        finally:
            db.close()

    def _schedule_jobs(self) -> None:
        """Schedule all periodic jobs."""
        # Reddit collection
        self._scheduler.add_job(
            self._collect_reddit_data_job,
            trigger=IntervalTrigger(
                minutes=self._settings.reddit_collection_interval_minutes
            ),
            id="reddit_collection",
            replace_existing=True,
        )

        # Price collection
        self._scheduler.add_job(
            self._collect_price_data_job,
            trigger=IntervalTrigger(
                minutes=self._settings.price_collection_interval_minutes
            ),
            id="price_collection",
            replace_existing=True,
        )

        # Daily analysis (once per day at configured hour)
        self._scheduler.add_job(
            self._run_daily_analysis_job,
            trigger=CronTrigger(hour=self._settings.daily_analysis_hour, minute=0),
            id="daily_analysis",
            replace_existing=True,
        )

        # Notification checks
        self._scheduler.add_job(
            self._check_notifications_job,
            trigger=IntervalTrigger(
                minutes=self._settings.notification_check_interval_minutes
            ),
            id="notification_check",
            replace_existing=True,
        )

    def _collect_reddit_data_job(self) -> None:
        """Scheduled job wrapper for Reddit collection."""
        db = SessionLocal()
        try:
            self._collect_reddit_data(db)
            job_repo = JobExecutionRepository(db)
            job_repo.record_run("reddit_collection")
            db.commit()
        except Exception as exc:
            logger.error(f"Error in Reddit collection job: {exc}", exc_info=True)
            db.rollback()
        finally:
            db.close()

    def _collect_reddit_data(self, db: Session) -> None:
        """Collect Reddit posts and save them to the database."""
        try:
            subreddits = [
                s.strip() for s in self._settings.reddit_subreddits.split(",")
            ]
            posts = self._reddit_service.fetch_recent_posts(
                subreddits, limit_per_subreddit=100, max_age=timedelta(days=2)
            )
        except ExternalAPIError as exc:
            logger.error(f"Failed to fetch Reddit posts: {exc}")
            return

        if not posts:
            logger.debug("No Reddit posts fetched")
            return

        # Get list of tracked stocks for ticker matching
        stock_repo = StockRepository(db)
        stocks = stock_repo.list()
        known_symbols = {s.symbol.upper() for s in stocks}

        reddit_repo = RedditPostRepository(db)
        saved_count = 0

        for post_data in posts:
            # Extract tickers from title
            tickers = extract_tickers(post_data.title, known_symbols)

            # If no ticker found, skip this post
            if not tickers:
                continue

            # Save post for each matching ticker
            for symbol in tickers:
                # Check if we already have this post for this symbol
                stmt = select(RedditPost).where(
                    RedditPost.id == post_data.id,
                    RedditPost.stock_symbol == symbol,
                )
                existing = db.execute(stmt).scalar_one_or_none()

                if existing is None:
                    reddit_post = RedditPost(
                        id=post_data.id,
                        stock_symbol=symbol,
                        subreddit=post_data.subreddit,
                        title=post_data.title,
                        author=post_data.author,
                        upvotes=post_data.upvotes,
                        comments=post_data.comments,
                        url=post_data.url,
                        posted_at=post_data.posted_at,
                        collected_at=post_data.collected_at,
                    )
                    reddit_repo.add(reddit_post)
                    saved_count += 1

        logger.info(f"Saved {saved_count} Reddit posts")

    def _collect_price_data_job(self) -> None:
        """Scheduled job wrapper for price collection."""
        db = SessionLocal()
        try:
            self._collect_price_data(db)
            job_repo = JobExecutionRepository(db)
            job_repo.record_run("price_collection")
            db.commit()
        except Exception as exc:
            logger.error(f"Error in price collection job: {exc}", exc_info=True)
            db.rollback()
        finally:
            db.close()

    def _collect_price_data(self, db: Session) -> None:
        """Collect price data for all tracked stocks."""
        stock_repo = StockRepository(db)
        price_repo = PriceDataRepository(db)
        stocks = stock_repo.list()

        if not stocks:
            logger.debug("No stocks to collect price data for")
            return

        saved_count = 0
        today = date.today()

        for stock in stocks:
            try:
                # Fetch last 30 days of data to ensure we have recent prices
                start_date = today - timedelta(days=30)
                bars = self._yahoo_service.fetch_historical_prices(
                    stock.symbol, start=start_date, end=today
                )
            except ExternalAPIError as exc:
                logger.warning(f"Failed to fetch price data for {stock.symbol}: {exc}")
                continue

            for bar in bars:
                # Check if we already have this date for this symbol
                existing = price_repo.get_for_date(bar.stock_symbol, bar.date)
                if existing is None:
                    price_data = PriceData(
                        stock_symbol=bar.stock_symbol,
                        date=bar.date,
                        open=bar.open,
                        high=bar.high,
                        low=bar.low,
                        close=bar.close,
                        volume=bar.volume,
                        timestamp=bar.source_timestamp,
                    )
                    price_repo.add(price_data)
                    saved_count += 1

        logger.info(f"Saved {saved_count} price data points")

    def _run_daily_analysis_job(self) -> None:
        """Scheduled job wrapper for daily analysis."""
        db = SessionLocal()
        try:
            self._run_daily_analysis(db)
            job_repo = JobExecutionRepository(db)
            job_repo.record_run("daily_analysis")
            db.commit()
        except Exception as exc:
            logger.error(f"Error in daily analysis job: {exc}", exc_info=True)
            db.rollback()
        finally:
            db.close()

    def _run_daily_analysis(self, db: Session) -> None:
        """Run daily analysis (this is a no-op that just triggers the analysis)."""
        # The analysis itself doesn't need to persist anything; it's computed
        # on-demand when the API is called. But we record that we "ran" it
        # for scheduling purposes.
        logger.info("Daily analysis job completed (results computed on-demand via API)")

    def _check_notifications_job(self) -> None:
        """Scheduled job wrapper for notification checks."""
        db = SessionLocal()
        try:
            self._check_notifications(db)
            job_repo = JobExecutionRepository(db)
            job_repo.record_run("notification_check")
            db.commit()
        except Exception as exc:
            logger.error(f"Error in notification check job: {exc}", exc_info=True)
            db.rollback()
        finally:
            db.close()

    def _check_notifications(self, db: Session) -> None:
        """Check all stocks and generate notifications for unusual activity."""
        stock_repo = StockRepository(db)
        stocks = stock_repo.list()

        total_notifications = 0
        for stock in stocks:
            try:
                notifications = generate_notifications_for_stock(db, stock.symbol)
                total_notifications += len(notifications)
            except Exception as exc:
                logger.warning(
                    f"Error generating notifications for {stock.symbol}: {exc}"
                )
                continue

        if total_notifications > 0:
            logger.info(f"Generated {total_notifications} notifications")
