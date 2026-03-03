"""Intraday minute-bar ingestion using Alpaca with free-plan-safe end times.

Batched, paged ingestion into a Parquet feature store with DB-backed ingestion
state. Uses compute_safe_end_time so we never query the last ~15 minutes when
on delayed SIP (free plan). All timestamps UTC.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.clients.alpaca_data_client import AlpacaDataClient
from backend.app.config import get_settings
from backend.app.data.repositories.intraday_ingest_repo import IntradayIngestRepository
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.feature_store.parquet_store import ParquetFeatureStore
from backend.app.utils.errors import ExternalAPIError, IngestionAlreadyRunningError

logger = logging.getLogger(__name__)

# Substrings in error messages that indicate systemic API/config failure (abort run, don't retry more symbols)
_SYSTEMIC_ERROR_INDICATORS = (
    "invalid feed",
    "subscription does not permit",
    "401",
    "403",
    "Unauthorized",
    "Forbidden",
)


def _is_systemic_api_error(exc: ExternalAPIError) -> bool:
    """True if error suggests config/auth/system issue—abort run instead of trying more symbols."""
    msg = (str(exc) or "").lower()
    return any(ind.lower() in msg for ind in _SYSTEMIC_ERROR_INDICATORS)


def _parse_bar_ts(bar: dict) -> datetime | None:
    """Return UTC datetime from bar 't' field."""
    import datetime as _dt

    t = bar.get("t")
    if t is None:
        return None
    if isinstance(t, _dt.datetime):
        return t.astimezone(_dt.timezone.utc) if t.tzinfo else t.replace(tzinfo=_dt.timezone.utc)
    s = str(t).replace("Z", "+00:00")
    dt = _dt.datetime.fromisoformat(s)
    return dt.astimezone(_dt.timezone.utc)


def run_intraday_ingestion(
    db: Session,
    universe: list[str] | None = None,
    owner: str = "scheduler",
) -> dict:
    """Run incremental intraday minute-bar ingestion for the given or default universe.

    Args:
        db: Database session (caller commits).
        universe: Optional list of symbols. If None, uses tracked stocks from DB.
        owner: Lock owner id (e.g. "scheduler" or "api:<uuid>") for governance.

    Returns:
        Run summary: symbols_processed, bars_written, errors_count, start_utc, end_utc,
        safe_end_used, feed, etc.

    Raises:
        IngestionAlreadyRunningError: When lock is enabled and another run holds the lock,
            or when heartbeat fails (lock lost).
    """
    settings = get_settings()
    lock_enabled = getattr(settings, "intraday_lock_enabled", True)
    lock_name = getattr(settings, "intraday_lock_name", "intraday_ingestion")
    lock_ttl = getattr(settings, "intraday_lock_ttl_seconds", 1800)

    if not lock_enabled:
        logger.warning("Intraday ingestion lock is disabled; overlapping runs are possible")

    client = AlpacaDataClient(
        free_plan_mode=settings.alpaca_free_plan_mode,
        end_time_safety_minutes=settings.alpaca_end_time_safety_minutes,
        feed=settings.alpaca_data_feed,
        api_key_id=settings.alpaca_api_key_id,
        api_secret_key=settings.alpaca_api_secret_key,
        base_url=settings.alpaca_data_base_url,
        min_request_interval_seconds=(
            mi if isinstance(mi := getattr(settings, "alpaca_min_request_interval_seconds", 0.0), (int, float)) else 0.0
        ),
    )
    now = datetime.now(timezone.utc)
    safe_end = client.compute_safe_end_time(now)

    # Resolve universe
    if universe is not None:
        symbols = list(universe)
    else:
        if settings.intraday_universe_mode != "tracked":
            logger.warning("intraday_universe_mode=%s; only 'tracked' is implemented", settings.intraday_universe_mode)
        stock_repo = StockRepository(db)
        stocks = stock_repo.list()
        symbols = [s.symbol for s in stocks]

    if not symbols:
        return {
            "symbols_processed": 0,
            "bars_written": 0,
            "errors_count": 0,
            "start_utc": None,
            "end_utc": safe_end.isoformat(),
            "safe_end_used": safe_end.isoformat(),
            "feed": settings.alpaca_data_feed,
            "free_plan_mode": settings.alpaca_free_plan_mode,
        }

    max_per_run = getattr(settings, "intraday_max_symbols_per_run", 0)
    if isinstance(max_per_run, int) and max_per_run > 0 and len(symbols) > max_per_run:
        symbols = symbols[:max_per_run]
        logger.info(
            "Intraday ingestion capped to %s symbols (intraday_max_symbols_per_run)",
            max_per_run,
        )

    repo = IntradayIngestRepository(db)
    lock_repo = None
    lock_acquired = False
    if lock_enabled:
        from backend.app.data.repositories.job_lock_repo import JobLockRepository

        lock_repo = JobLockRepository(db)
        if not lock_repo.try_acquire_lock(lock_name, owner, lock_ttl, now):
            current = lock_repo.get_lock(lock_name)
            owner_str = current.owner if current else "unknown"
            expires_str = current.expires_at.isoformat() if current and current.expires_at else None
            raise IngestionAlreadyRunningError(
                "Intraday ingestion already in progress",
                owner=owner_str,
                expires_at=expires_str,
            )
        lock_acquired = True
    else:
        running = repo.get_running_run()
        if running is not None:
            logger.warning(
                "Intraday ingestion lock disabled; another run in progress (run_id=%s) - failing explicitly",
                running.id,
            )
            raise IngestionAlreadyRunningError(
                "Intraday ingestion already in progress (lock disabled; run state detected)",
                owner=f"run_id:{running.id}",
                expires_at=None,
            )

    repo.ensure_symbols(symbols)
    db.commit()

    run = repo.create_run(symbols_count=len(symbols), notes=None)
    db.commit()

    store_root = Path(settings.intraday_feature_store_root)
    store_root.mkdir(parents=True, exist_ok=True)
    store = ParquetFeatureStore(str(store_root), source="alpaca")
    batch_size = settings.intraday_symbols_batch_size
    lookback_days = settings.intraday_lookback_days
    max_pages = settings.intraday_max_pages_per_batch

    states = repo.get_states(symbols)
    total_bars = 0
    errors_count = 0
    start_utc_used: datetime | None = None
    abort_run = False

    try:
        for i in range(0, len(symbols), batch_size):
            if abort_run:
                logger.warning("Aborting intraday run due to systemic API error; skipping remaining batches")
                break
            batch = symbols[i : i + batch_size]  # noqa: E203 (black style)
            # Compute start/end per symbol for this batch (same end for all: safe_end)
            symbol_starts: dict[str, datetime] = {}
            for sym in batch:
                st = states.get(sym)
                if st and st.status == "paused":
                    continue
                if st and st.last_ts is not None:
                    # next minute after last
                    last = st.last_ts
                    if last.tzinfo is None:
                        last = last.replace(tzinfo=timezone.utc)
                    start_sym = last + timedelta(minutes=1)
                else:
                    start_sym = safe_end - timedelta(days=lookback_days)
                if start_sym >= safe_end:
                    continue
                symbol_starts[sym] = start_sym
                if start_utc_used is None or start_sym < start_utc_used:
                    start_utc_used = start_sym

            if not symbol_starts:
                continue

            batch_list = sorted(symbol_starts.keys(), key=lambda s: symbol_starts[s])
            # Use single start/end for the batch (min start, safe_end)
            batch_start = min(symbol_starts[s] for s in batch_list)
            page_token: str | None = None
            pages_done = 0
            max_ts_by_symbol: dict[str, datetime] = {}

            while pages_done < max_pages:
                try:
                    bars_page, page_token = client.fetch_bars_page(
                        symbols=batch_list,
                        start=batch_start,
                        end=safe_end,
                        timeframe="1Min",
                        feed=settings.alpaca_data_feed,
                        page_token=page_token,
                        limit=10000,
                    )
                except ExternalAPIError as e:
                    logger.error("Alpaca fetch failed for batch: %s", e)
                    for sym in batch_list:
                        repo.mark_error(sym, str(e))
                        errors_count += 1
                    if _is_systemic_api_error(e):
                        abort_run = True
                        logger.error(
                            "Systemic API error detected (config/auth/feed); aborting run to avoid hammering %s symbols",
                            len(symbols) - (i + len(batch)),
                        )
                    break

                if not bars_page:
                    if page_token:
                        pages_done += 1
                        continue
                    break

                try:
                    written = store.write_bars(bars_page)
                    total_bars += written
                except Exception as e:
                    logger.exception("Parquet write failed: %s", e)
                    for sym in bars_page.keys():
                        repo.mark_error(sym, str(e))
                        errors_count += 1
                    break

                for sym, bar_list in bars_page.items():
                    for b in bar_list:
                        ts = _parse_bar_ts(b)
                        if ts and (sym not in max_ts_by_symbol or ts > max_ts_by_symbol[sym]):
                            max_ts_by_symbol[sym] = ts

                pages_done += 1
                if not page_token:
                    break

            # Persist last_ts for symbols we got data for
            for sym, ts in max_ts_by_symbol.items():
                try:
                    repo.update_success(sym, ts)
                except Exception as e:
                    logger.warning("Failed to update state for %s: %s", sym, e)
                    repo.mark_error(sym, str(e))
                    errors_count += 1

            # Heartbeat to keep lock alive (extend lease by full TTL)
            if lock_acquired and lock_repo:
                if not lock_repo.heartbeat(lock_name, owner, lock_ttl, datetime.now(timezone.utc)):
                    raise IngestionAlreadyRunningError(
                        "Intraday ingestion lock lost (heartbeat failed); aborting.",
                        owner=owner,
                        expires_at=None,
                    )
    finally:
        if lock_acquired and lock_repo:
            lock_repo.release_lock(lock_name, owner)
        repo.finish_run(
            run.id,
            bars_written=total_bars,
            errors_count=errors_count,
            notes=None,
        )
        db.commit()

    logger.info(
        "Intraday ingestion: symbols=%s bars_written=%s errors=%s safe_end=%s",
        len(symbols),
        total_bars,
        errors_count,
        safe_end.isoformat(),
    )

    return {
        "symbols_processed": len(symbols),
        "bars_written": total_bars,
        "errors_count": errors_count,
        "start_utc": start_utc_used.isoformat() if start_utc_used else None,
        "end_utc": safe_end.isoformat(),
        "safe_end_used": safe_end.isoformat(),
        "feed": settings.alpaca_data_feed,
        "free_plan_mode": settings.alpaca_free_plan_mode,
    }
