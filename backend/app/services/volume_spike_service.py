"""Backfill volume spike events from daily price_data (015)."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.data.repositories.volume_spike_event_repo import VolumeSpikeEventRepository
from backend.app.models.price_data import PriceData
from backend.app.models.volume_spike_event import VolumeSpikeEvent
from backend.app.services.volume_spike_detection import (
    classify_event_type,
    compute_baseline_volume,
    compute_same_day_return_pct,
    is_volume_spike,
)

logger = logging.getLogger(__name__)


def backfill_volume_spikes(
    db: Session,
    start_date: date,
    end_date: date,
    symbols: list[str] | None = None,
    replace_range: bool = False,
) -> dict[str, Any]:
    """Scan [start_date, end_date] per symbol; upsert volume_spike_events."""
    if start_date > end_date:
        raise ValueError("start_date must be <= end_date")

    settings = get_settings()
    W = max(1, int(settings.volume_spike_research_baseline_window_days))
    stat = settings.volume_spike_research_baseline_statistic or "median"
    ratio_t = float(settings.volume_spike_research_ratio_threshold)
    flat_band = float(settings.volume_spike_research_flat_band_pct)
    min_close = float(settings.volume_spike_research_min_close or 0)
    min_baseline = float(settings.volume_spike_research_min_baseline_volume or 0)

    stock_repo = StockRepository(db)
    price_repo = PriceDataRepository(db)
    spike_repo = VolumeSpikeEventRepository(db)

    if symbols:
        sym_list = [s.strip().upper() for s in symbols if s.strip()]
    else:
        sym_list = [s.symbol for s in stock_repo.list()]

    if replace_range:
        deleted = spike_repo.delete_in_date_range(start_date, end_date, sym_list if symbols else None)
        db.commit()
        logger.info("volume_spike backfill replace_range: deleted %s rows", deleted)

    events_written = 0
    days_scanned = 0
    skipped_no_data = 0

    for sym in sym_list:
        bars = price_repo.list_for_stock(sym)
        if len(bars) < W + 1:
            continue
        sorted_bars: list[PriceData] = sorted(bars, key=lambda b: b.date)
        sorted_dates = [b.date for b in sorted_bars]
        by_date = {b.date: b for b in sorted_bars}

        for i, d in enumerate(sorted_dates):
            if d < start_date or d > end_date:
                continue
            days_scanned += 1
            if i < W:
                skipped_no_data += 1
                continue
            bar = by_date[d]
            prior_volumes = [by_date[sorted_dates[j]].volume for j in range(i - W, i)]
            baseline = compute_baseline_volume(prior_volumes, stat)
            if baseline is None:
                skipped_no_data += 1
                continue
            if min_baseline > 0 and baseline < min_baseline:
                continue
            if min_close > 0 and bar.close < min_close:
                continue
            if not is_volume_spike(bar.volume, baseline, ratio_t):
                continue
            prev_bar = by_date[sorted_dates[i - 1]]
            ret = compute_same_day_return_pct(float(bar.close), float(prev_bar.close))
            if ret is None:
                logger.debug("Skip %s %s: invalid same-day return inputs", sym, d)
                continue
            etype = classify_event_type(ret, flat_band)
            ratio = round(bar.volume / baseline, 6)
            ev = VolumeSpikeEvent(
                symbol=sym,
                event_date=d,
                volume=bar.volume,
                baseline_volume=baseline,
                volume_ratio=ratio,
                same_day_return_pct=ret,
                event_type=etype,
            )
            spike_repo.upsert(ev)
            events_written += 1

    db.commit()
    return {
        "events_upserted": events_written,
        "trading_days_considered": days_scanned,
        "skipped_short_history_or_baseline": skipped_no_data,
        "symbols_processed": len(sym_list),
    }
