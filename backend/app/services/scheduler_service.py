from __future__ import annotations

import logging
from typing import Any
import threading
from datetime import date, datetime, time, timedelta, timezone

from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.data.database import SessionLocal
from backend.app.data.repositories.job_execution_repo import JobExecutionRepository
from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.models.price_data import PriceData
from backend.app.services.intraday_ingestion_service import run_intraday_ingestion
from backend.app.services.notification_service import generate_notifications_for_stock
from backend.app.services.leader_follower_service import run_detection
from backend.app.services.yahoo_service import YahooFinanceService
from backend.app.utils.errors import ExternalAPIError

logger = logging.getLogger(__name__)


class SchedulerService:
    """Manages scheduled background jobs with catch-up support.

    On startup, the scheduler and periodic jobs start immediately so the app
    can serve requests. Catch-up (if enabled) runs in a separate thread so
    it does not block startup. All errors are logged but do not stop the scheduler.
    """

    def __init__(self) -> None:
        self._scheduler = BackgroundScheduler()
        self._settings = get_settings()
        self._yahoo_service = YahooFinanceService()

    def start(self) -> None:
        """Start the scheduler; run catch-up in background if enabled."""
        # Schedule periodic jobs and start scheduler so the app is ready to serve
        self._schedule_jobs()
        self._scheduler.start()
        logger.info("Scheduler started")

        if self._settings.enable_catch_up:
            thread = threading.Thread(target=self._run_catch_up_guarded, daemon=True)
            thread.start()
            logger.info("Catch-up running in background")

    def shutdown(self) -> None:
        """Shutdown the scheduler gracefully."""
        self._scheduler.shutdown()
        logger.info("Scheduler stopped")

    def _record_job_failure(
        self,
        job_name: str,
        exc: BaseException,
        *,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        duration_seconds: float | None = None,
        summary: str | None = None,
        metrics: dict[str, object] | None = None,
    ) -> None:
        """Record a failed run in a separate session so rollback does not affect it."""
        db = SessionLocal()
        try:
            job_repo = JobExecutionRepository(db)
            run_at = finished_at or datetime.now(timezone.utc)
            err_msg = str(exc)[:500]
            summary_val = summary or f"failed: {err_msg[:100]}"
            metrics_val = metrics or {"error_truncated": err_msg[:200]}
            job_repo.record_run(
                job_name,
                run_at=run_at,
                success=False,
                error_message=err_msg,
                started_at=started_at,
                duration_seconds=duration_seconds,
                summary=summary_val,
                metrics=metrics_val,
            )
            db.commit()
        except Exception as record_exc:
            logger.warning("Failed to record job failure for %s: %s", job_name, record_exc)
        finally:
            db.close()

    def _run_catch_up_guarded(self) -> None:
        """Run catch-up in a background thread; log and swallow exceptions."""
        try:
            logger.info("Running catch-up for missed jobs...")
            self._run_catch_up()
        except Exception as exc:
            logger.error(f"Error during catch-up: {exc}", exc_info=True)

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

            tz = ZoneInfo(self._settings.market_timezone)
            local_today = datetime.now(tz).date()
            local_today_start = datetime.combine(local_today, time.min, tzinfo=tz)
            today_start_utc = local_today_start.astimezone(timezone.utc)

            # Check price collection
            last_price = ensure_timezone_aware(job_repo.get_last_run("price_collection"))
            if last_price is None or (now - last_price).total_seconds() > 900:
                logger.info("Catching up on price collection...")
                started = datetime.now(timezone.utc)
                price_stats: dict[str, Any] = dict(self._collect_price_data(db))
                finished = datetime.now(timezone.utc)
                rows_inserted = price_stats.get("rows_inserted", 0)
                symbols = price_stats.get("symbols", 0)
                summary = f"prices: {rows_inserted} rows inserted for {symbols} symbols"
                job_repo.record_run(
                    "price_collection",
                    run_at=finished,
                    success=True,
                    started_at=started,
                    duration_seconds=(finished - started).total_seconds(),
                    summary=summary,
                    metrics=price_stats,
                )
                db.commit()

            # Check daily analysis (run if we haven't run one today, in market timezone)
            last_analysis = ensure_timezone_aware(job_repo.get_last_run("daily_analysis"))
            if last_analysis is None or last_analysis < today_start_utc:
                logger.info("Catching up on daily analysis...")
                started = datetime.now(timezone.utc)
                analysis_stats: dict[str, Any] = dict(self._run_daily_analysis(db))
                finished = datetime.now(timezone.utc)
                symbols = analysis_stats.get("symbols_processed", 0)
                summary = f"analysis: RSI updated for {symbols} symbols"
                job_repo.record_run(
                    "daily_analysis",
                    run_at=finished,
                    success=True,
                    started_at=started,
                    duration_seconds=(finished - started).total_seconds(),
                    summary=summary,
                    metrics=analysis_stats,
                )
                db.commit()

            # Check notifications
            last_notif = ensure_timezone_aware(job_repo.get_last_run("notification_check"))
            if last_notif is None or (now - last_notif).total_seconds() > 1800:
                logger.info("Catching up on notification checks...")
                started = datetime.now(timezone.utc)
                stats = self._check_notifications(db)
                finished = datetime.now(timezone.utc)
                notifs = stats.get("notifications_generated", 0)
                symbols = stats.get("symbols_checked", 0)
                summary = f"notifications: {notifs} generated for {symbols} symbols"
                job_repo.record_run(
                    "notification_check",
                    run_at=finished,
                    success=True,
                    started_at=started,
                    duration_seconds=(finished - started).total_seconds(),
                    summary=summary,
                    metrics=stats,
                )
                db.commit()

        except Exception as exc:
            logger.error(f"Error during catch-up: {exc}", exc_info=True)
            db.rollback()
        finally:
            db.close()

    def _schedule_jobs(self) -> None:
        """Schedule all periodic jobs."""
        # Price collection
        self._scheduler.add_job(
            self._collect_price_data_job,
            trigger=IntervalTrigger(minutes=self._settings.price_collection_interval_minutes),
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
            trigger=IntervalTrigger(minutes=self._settings.notification_check_interval_minutes),
            id="notification_check",
            replace_existing=True,
        )

        # Intraday minute-bar ingestion (when enabled; no overlap)
        if getattr(self._settings, "intraday_ingestion_enabled", False):
            self._scheduler.add_job(
                self._intraday_ingestion_job,
                trigger=IntervalTrigger(minutes=getattr(self._settings, "intraday_interval_minutes", 15)),
                id="intraday_ingestion",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=900,
                next_run_time=datetime.now(timezone.utc),
            )

        # Leader-follower signal detection (when enabled; once per day)
        if getattr(self._settings, "leader_follower_enabled", False):
            self._scheduler.add_job(
                self._leader_follower_detection_job,
                trigger=CronTrigger(
                    hour=getattr(self._settings, "leader_follower_job_hour", 17),
                    minute=0,
                ),
                id="leader_follower_detection",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=1800,
            )

    def _collect_price_data_job(self) -> None:
        """Scheduled job wrapper for price collection."""
        db = SessionLocal()
        started_at = datetime.now(timezone.utc)
        try:
            stats = self._collect_price_data(db)
            finished_at = datetime.now(timezone.utc)
            duration = (finished_at - started_at).total_seconds()
            rows_inserted = stats.get("rows_inserted", 0)
            symbols = stats.get("symbols", 0)
            summary = f"prices: {rows_inserted} rows inserted for {symbols} symbols"
            job_repo = JobExecutionRepository(db)
            job_repo.record_run(
                "price_collection",
                run_at=finished_at,
                success=True,
                started_at=started_at,
                duration_seconds=duration,
                summary=summary,
                metrics=stats,
            )
            db.commit()
        except Exception as exc:
            logger.error(f"Error in price collection job: {exc}", exc_info=True)
            db.rollback()
            finished_at = datetime.now(timezone.utc)
            duration = (finished_at - started_at).total_seconds()
            self._record_job_failure(
                "price_collection",
                exc,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration,
            )
        finally:
            db.close()

    def _collect_price_data(self, db: Session) -> dict[str, int | str]:
        """Collect price data for all tracked stocks. Returns metrics dict."""
        stock_repo = StockRepository(db)
        price_repo = PriceDataRepository(db)
        stocks = stock_repo.list()

        if not stocks:
            logger.debug("No stocks to collect price data for")
            return {"symbols": 0, "rows_inserted": 0, "provider": "yfinance"}

        saved_count = 0
        today = date.today()

        for stock in stocks:
            try:
                start_date = today - timedelta(days=self._settings.price_history_days)
                bars = self._yahoo_service.fetch_historical_prices(stock.symbol, start=start_date, end=today)
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

            # Commit after each stock to release DB lock (allows other jobs e.g. leader-follower to write)
            db.commit()

        logger.info(f"Saved {saved_count} price data points")
        return {
            "symbols": len(stocks),
            "rows_inserted": saved_count,
            "provider": "yfinance",
        }

    def _run_daily_analysis_job(self) -> None:
        """Scheduled job wrapper for daily analysis."""
        db = SessionLocal()
        started_at = datetime.now(timezone.utc)
        try:
            stats = self._run_daily_analysis(db)
            finished_at = datetime.now(timezone.utc)
            duration = (finished_at - started_at).total_seconds()
            symbols = stats.get("symbols_processed", 0)
            summary = f"analysis: RSI updated for {symbols} symbols"
            job_repo = JobExecutionRepository(db)
            job_repo.record_run(
                "daily_analysis",
                run_at=finished_at,
                success=True,
                started_at=started_at,
                duration_seconds=duration,
                summary=summary,
                metrics=stats,
            )
            db.commit()
        except Exception as exc:
            logger.error(f"Error in daily analysis job: {exc}", exc_info=True)
            db.rollback()
            finished_at = datetime.now(timezone.utc)
            duration = (finished_at - started_at).total_seconds()
            self._record_job_failure(
                "daily_analysis",
                exc,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration,
            )
        finally:
            db.close()

    def _run_daily_analysis(self, db: Session) -> dict[str, object]:
        """Run daily analysis. Results computed on-demand via API; returns minimal metrics."""
        logger.info("Daily analysis job completed (results computed on-demand via API)")
        return {"symbols_processed": 0, "indicators": {}}

    def _check_notifications_job(self) -> None:
        """Scheduled job wrapper for notification checks."""
        db = SessionLocal()
        started_at = datetime.now(timezone.utc)
        try:
            stats = self._check_notifications(db)
            finished_at = datetime.now(timezone.utc)
            duration = (finished_at - started_at).total_seconds()
            notifs = stats.get("notifications_generated", 0)
            symbols = stats.get("symbols_checked", 0)
            summary = f"notifications: {notifs} generated for {symbols} symbols"
            job_repo = JobExecutionRepository(db)
            job_repo.record_run(
                "notification_check",
                run_at=finished_at,
                success=True,
                started_at=started_at,
                duration_seconds=duration,
                summary=summary,
                metrics=stats,
            )
            db.commit()
        except Exception as exc:
            logger.error(f"Error in notification check job: {exc}", exc_info=True)
            db.rollback()
            finished_at = datetime.now(timezone.utc)
            duration = (finished_at - started_at).total_seconds()
            self._record_job_failure(
                "notification_check",
                exc,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration,
            )
        finally:
            db.close()

    def _check_notifications(self, db: Session) -> dict[str, int]:
        """Check all stocks and generate notifications for unusual activity. Returns metrics."""
        stock_repo = StockRepository(db)
        stocks = stock_repo.list()

        total_notifications = 0
        for stock in stocks:
            try:
                notifications = generate_notifications_for_stock(db, stock.symbol)
                total_notifications += len(notifications)
            except Exception as exc:
                logger.warning(f"Error generating notifications for {stock.symbol}: {exc}")
                continue

        if total_notifications > 0:
            logger.info(f"Generated {total_notifications} notifications")
        return {
            "symbols_checked": len(stocks),
            "notifications_generated": total_notifications,
        }

    def _intraday_ingestion_job(self) -> None:
        """Scheduled job for intraday minute-bar ingestion (batched, incremental)."""
        db = SessionLocal()
        started_at = datetime.now(timezone.utc)
        try:
            stats = run_intraday_ingestion(db, universe=None)
            finished_at = datetime.now(timezone.utc)
            duration = (finished_at - started_at).total_seconds()
            bars_written = stats.get("bars_written", 0)
            symbols = stats.get("symbols_processed", 0)
            summary_str = f"intraday: {bars_written} bars written for {symbols} symbols"
            job_repo = JobExecutionRepository(db)
            job_repo.record_run(
                "intraday_ingestion",
                run_at=finished_at,
                success=True,
                started_at=started_at,
                duration_seconds=duration,
                summary=summary_str,
                metrics=stats,
            )
            db.commit()
            logger.info(
                "Intraday ingestion job: bars_written=%s errors=%s symbols=%s safe_end=%s",
                bars_written,
                stats.get("errors_count", 0),
                symbols,
                stats.get("safe_end_used", ""),
            )
        except Exception as exc:
            logger.error("Error in intraday ingestion job: %s", exc, exc_info=True)
            db.rollback()
            finished_at = datetime.now(timezone.utc)
            duration = (finished_at - started_at).total_seconds()
            self._record_job_failure(
                "intraday_ingestion", exc, started_at=started_at, finished_at=finished_at, duration_seconds=duration
            )
        finally:
            db.close()

    def _leader_follower_detection_job(self) -> None:
        """Scheduled job: detect leaders, select followers, create signals."""
        db = SessionLocal()
        started_at = datetime.now(timezone.utc)
        job_repo = JobExecutionRepository(db)
        run_id = job_repo.insert_run_start("leader_follower_detection", started_at=started_at)
        db.commit()  # Persist run row so it survives rollback on failure
        try:
            # Warn if stock_groups empty; follower candidates will be zero
            from backend.app.data.repositories.stock_group_repo import StockGroupRepository

            sg_repo = StockGroupRepository(db)
            if sg_repo.count_total() == 0:
                logger.warning(
                    "stock_groups is empty; leader detection may work but follower "
                    "candidate generation will return zero. Run: python -m backend.app.cli seed stock-groups"
                )
            metrics = run_detection(db, run_id=run_id)
            finished_at = datetime.now(timezone.utc)
            duration = (finished_at - started_at).total_seconds()
            leaders = metrics.get("leader_events_detected", 0)
            signals = metrics.get("signals_emitted", 0)
            summary = f"leader-follower: {leaders} leaders, {signals} signals"
            job_repo.complete_run(
                run_id,
                success=True,
                run_at=finished_at,
                duration_seconds=duration,
                summary=summary,
                metrics=metrics,
            )
            db.commit()
        except Exception as exc:
            logger.error("Error in leader-follower detection job: %s", exc, exc_info=True)
            db.rollback()
            finished_at = datetime.now(timezone.utc)
            duration = (finished_at - started_at).total_seconds()
            job_repo.complete_run(
                run_id,
                success=False,
                run_at=finished_at,
                duration_seconds=duration,
                error_message=str(exc)[:500],
            )
            db.commit()
            self._record_job_failure(
                "leader_follower_detection",
                exc,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration,
            )
        finally:
            db.close()
