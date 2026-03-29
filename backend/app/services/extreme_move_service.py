"""Backfill extreme move events from daily price_data (016)."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.data.repositories.extreme_move_event_repo import ExtremeMoveEventRepository
from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.models.extreme_move_event import ExtremeMoveEvent
from backend.app.models.price_data import PriceData
from backend.app.services.extreme_move_detection import (
    classify_extreme_move,
    compute_daily_return_pct,
    get_magnitude_bucket,
    get_volume_bucket,
)
from backend.app.services.volume_spike_detection import compute_baseline_volume

logger = logging.getLogger(__name__)


def backfill_extreme_moves(
    db: Session,
    start_date: date,
    end_date: date,
    symbols: list[str] | None = None,
    replace_range: bool = False,
) -> dict[str, Any]:
    """Scan [start_date, end_date] per symbol; upsert extreme_move_events."""
    if start_date > end_date:
        raise ValueError("start_date must be <= end_date")

    settings = get_settings()
    up_th = float(settings.extreme_move_up_threshold_pct)
    down_th = float(settings.extreme_move_down_threshold_pct)
    min_close = float(getattr(settings, "extreme_move_research_min_close", 0) or 0)
    W = max(1, int(settings.volume_spike_research_baseline_window_days))
    vol_stat = settings.volume_spike_research_baseline_statistic or "median"
    min_baseline_vol = float(settings.volume_spike_research_min_baseline_volume or 0)
    vol_high_r = float(settings.extreme_move_context_volume_high_ratio)
    vol_extreme_r = float(settings.extreme_move_context_volume_extreme_ratio)

    stock_repo = StockRepository(db)
    price_repo = PriceDataRepository(db)
    event_repo = ExtremeMoveEventRepository(db)

    if symbols:
        sym_list = [s.strip().upper() for s in symbols if s.strip()]
    else:
        sym_list = [s.symbol for s in stock_repo.list()]

    if replace_range:
        deleted = event_repo.delete_in_date_range(start_date, end_date, sym_list if symbols else None)
        db.commit()
        logger.info("extreme_move backfill replace_range: deleted %s rows", deleted)

    events_written = 0
    days_scanned = 0
    skipped_no_prev = 0

    for sym in sym_list:
        bars = price_repo.list_for_stock(sym)
        if len(bars) < 2:
            continue
        sorted_bars: list[PriceData] = sorted(bars, key=lambda b: b.date)
        sorted_dates = [b.date for b in sorted_bars]
        by_date = {b.date: b for b in sorted_bars}

        for i, d in enumerate(sorted_dates):
            if d < start_date or d > end_date:
                continue
            if i < 1:
                skipped_no_prev += 1
                continue
            days_scanned += 1
            bar = by_date[d]
            prev_bar = by_date[sorted_dates[i - 1]]
            if min_close > 0 and bar.close < min_close:
                continue
            ret = compute_daily_return_pct(float(bar.close), float(prev_bar.close))
            if ret is None:
                skipped_no_prev += 1
                continue
            etype = classify_extreme_move(ret, up_th, down_th)
            if etype is None:
                continue
            mag = get_magnitude_bucket(ret)
            if i < W:
                vol_ratio: float | None = None
                vol_bucket = get_volume_bucket(None, vol_high_r, vol_extreme_r)
            else:
                prior_vols = [by_date[sorted_dates[j]].volume for j in range(i - W, i)]
                baseline = compute_baseline_volume(prior_vols, vol_stat)
                if baseline is not None and (min_baseline_vol <= 0 or baseline >= min_baseline_vol):
                    vol_ratio = round(float(bar.volume) / baseline, 4)
                else:
                    vol_ratio = None
                vol_bucket = get_volume_bucket(vol_ratio, vol_high_r, vol_extreme_r)
            ev = ExtremeMoveEvent(
                symbol=sym,
                event_date=d,
                return_pct=ret,
                event_type=etype,
                magnitude_bucket=mag,
                volume_ratio=vol_ratio,
                volume_bucket=vol_bucket,
            )
            event_repo.upsert(ev)
            events_written += 1

    db.commit()
    return {
        "events_upserted": events_written,
        "trading_days_considered": days_scanned,
        "skipped_no_prior_bar_or_invalid": skipped_no_prev,
        "symbols_processed": len(sym_list),
    }
