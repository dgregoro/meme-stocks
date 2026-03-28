"""Leader-follower historical backfill and replay.

Replays detection across a date range using Alpaca daily bars for PriceData.
Supports dry-run (no persist) and persist (idempotent) modes.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, cast, SupportsIndex

from sqlalchemy import delete
from sqlalchemy.orm import Session

from backend.app.clients.alpaca_data_client import AlpacaDataClient
from backend.app.config import get_settings
from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.data.repositories.stock_group_repo import StockGroupRepository
from backend.app.models.leader_follower_signal import LeaderFollowerSignal
from backend.app.models.price_data import PriceData
from backend.app.services.leader_follower_service import run_detection_for_date
from backend.app.utils.errors import ExternalAPIError

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 10  # Ensure enough bars for MIN_BARS_FOR_LEADER + buffer


def expand_backfill_symbols_with_regime_benchmarks(group_symbols: list[str], extra_symbols_csv: str) -> list[str]:
    """Append regime benchmark tickers (014) so replay backfill fetches SPY (etc.) alongside the group universe."""
    extra = [s.strip().upper() for s in extra_symbols_csv.split(",") if s.strip()]
    return list(dict.fromkeys(list(group_symbols) + extra))


def _parse_bar_date(bar: dict) -> date | None:
    """Extract date from Alpaca bar 't' field."""
    t = bar.get("t")
    if t is None:
        return None
    if isinstance(t, datetime):
        return t.date()  # type: ignore[union-attr]
    s = str(t).replace("Z", "+00:00")[:10]
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _trading_days(start: date, end: date) -> list[date]:
    """Yield trading days in [start, end], skipping weekends."""
    out: list[date] = []
    d = start
    while d <= end:
        if d.weekday() < 5:  # Mon=0 .. Fri=4
            out.append(d)
        d += timedelta(days=1)
    return out


def backfill_price_data_from_alpaca(
    db: Session,
    symbols: list[str],
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    """Fetch Alpaca daily bars for symbols over [start_date, end_date] and persist to PriceData.

    Returns: rows_inserted, symbols_fetched, errors (list).
    """
    settings = get_settings()
    if not settings.alpaca_api_key_id or not settings.alpaca_api_secret_key:
        raise ExternalAPIError("Alpaca API keys not configured (ALPACA_API_KEY_ID, ALPACA_API_SECRET_KEY)")

    client = AlpacaDataClient(
        free_plan_mode=settings.alpaca_free_plan_mode,
        end_time_safety_minutes=settings.alpaca_end_time_safety_minutes,
        feed=settings.alpaca_bars_feed,
        api_key_id=settings.alpaca_api_key_id,
        api_secret_key=settings.alpaca_api_secret_key,
        base_url=settings.alpaca_data_base_url,
    )
    price_repo = PriceDataRepository(db)
    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date, datetime.max.time().replace(hour=23, minute=59), tzinfo=timezone.utc)

    rows_inserted = 0
    errors: list[str] = []
    batch_size = 20
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i : i + batch_size]
        try:
            all_bars: dict[str, list[dict]] = {}
            page_token: str | None = None
            while True:
                bars_page, page_token = client.fetch_bars_page(
                    symbols=batch,
                    start=start_dt,
                    end=end_dt,
                    timeframe="1Day",
                    feed=client._feed,
                    page_token=page_token,
                    limit=10000,
                )
                for sym, bar_list in bars_page.items():
                    all_bars.setdefault(sym, []).extend(bar_list)
                if not page_token:
                    break

            for sym, bar_list in all_bars.items():
                for b in bar_list:
                    bar_date = _parse_bar_date(b)
                    if bar_date is None:
                        continue
                    if price_repo.get_for_date(sym, bar_date) is not None:
                        continue
                    try:
                        o = float(b.get("o", 0) or 0)
                        h = float(b.get("h", 0) or 0)
                        l_ = float(b.get("l", 0) or 0)
                        c = float(b.get("c", 0) or 0)
                        v = int(b.get("v", 0) or 0)
                    except (TypeError, ValueError):
                        continue
                    if c <= 0:
                        continue
                    row = PriceData(
                        stock_symbol=sym,
                        date=bar_date,
                        open=o,
                        high=h,
                        low=l_,
                        close=c,
                        volume=v,
                    )
                    price_repo.add(row)
                    rows_inserted += 1
            db.commit()
        except ExternalAPIError as e:
            errors.append(f"Alpaca fetch for {batch}: {e}")
            logger.warning("Alpaca fetch failed for batch: %s", e)
            db.rollback()
        except Exception as e:
            errors.append(f"Unexpected error for {batch}: {e}")
            logger.exception("Unexpected error fetching Alpaca bars")
            db.rollback()

    return {
        "rows_inserted": rows_inserted,
        "symbols_fetched": len(symbols),
        "errors": errors,
    }


def run_backfill(
    db: Session,
    start_date: date,
    end_date: date,
    *,
    dry_run: bool = False,
    persist: bool = True,
    replace_range: bool = False,
) -> dict[str, Any]:
    """Replay leader-follower detection over [start_date, end_date].

    Returns ReplaySummary.
    """
    stock_group_repo = StockGroupRepository(db)
    group_symbols = stock_group_repo.get_all_symbols()
    if not group_symbols:
        return {
            "days_processed": 0,
            "days_skipped": 0,
            "leaders_detected": 0,
            "candidates_found": 0,
            "signals_emitted": 0,
            "signals_skipped_duplicate": 0,
            "missing_data_warnings": ["stock_groups is empty"],
            "errors": [],
        }

    symbols = expand_backfill_symbols_with_regime_benchmarks(
        group_symbols,
        get_settings().leader_follower_regime_backfill_symbols,
    )

    if replace_range and persist:
        stmt = delete(LeaderFollowerSignal).where(
            LeaderFollowerSignal.signal_date >= start_date,
            LeaderFollowerSignal.signal_date <= end_date,
        )
        db.execute(stmt)
        db.commit()
        logger.info("Deleted existing signals in range %s to %s", start_date, end_date)

    lookback_start = start_date - timedelta(days=LOOKBACK_DAYS)
    backfill_result = backfill_price_data_from_alpaca(db, symbols, lookback_start, end_date)
    if backfill_result["errors"]:
        return {
            "days_processed": 0,
            "days_skipped": 0,
            "leaders_detected": 0,
            "candidates_found": 0,
            "signals_emitted": 0,
            "signals_skipped_duplicate": 0,
            "missing_data_warnings": [],
            "errors": backfill_result["errors"],
        }

    trading_days = _trading_days(start_date, end_date)
    days_processed = 0
    days_skipped = 0
    total_leaders = 0
    total_candidates = 0
    total_signals = 0
    total_skipped = 0
    missing_warnings: list[str] = []
    errors: list[str] = []

    for d in trading_days:
        try:
            metrics = run_detection_for_date(db, d, run_id=None, idempotent=persist and not replace_range)
            total_leaders += int(cast(SupportsIndex, metrics.get("leader_events_detected", 0) or 0))
            total_candidates += int(cast(SupportsIndex, metrics.get("follower_candidates_found", 0) or 0))
            total_signals += int(cast(SupportsIndex, metrics.get("signals_emitted", 0) or 0))
            total_skipped += int(cast(SupportsIndex, metrics.get("signals_skipped_duplicate", 0) or 0))
            days_processed += 1
            if dry_run:
                db.rollback()
            else:
                db.commit()
        except Exception as exc:
            db.rollback()
            errors.append(f"{d}: {exc}")
            logger.warning("Replay failed for %s: %s", d, exc)
            days_skipped += 1

    return {
        "days_processed": days_processed,
        "days_skipped": days_skipped,
        "leaders_detected": total_leaders,
        "candidates_found": total_candidates,
        "signals_emitted": total_signals,
        "signals_skipped_duplicate": total_skipped,
        "missing_data_warnings": missing_warnings,
        "errors": errors,
    }
