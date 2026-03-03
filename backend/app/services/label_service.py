"""Compute and store forward-return labels from PriceData.

Labels use strictly future prices: fwd_return = close[target] / close[D] - 1.
Horizon h is in trading days (sessions), not calendar days.
No look-ahead: label exists only when both close[D] and close[target] exist in PriceData.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy.orm import Session

from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.data.repositories.price_label_repo import PriceLabelRepository

logger = logging.getLogger(__name__)


def compute_and_store_forward_returns(
    db: Session,
    start_day: date,
    end_day: date,
    horizons: list[int] | None = None,
) -> dict[str, int | str]:
    """Compute forward returns for [start_day, end_day] and persist to price_labels.

    Horizon h is in trading days (sessions), not calendar days.

    Algorithm per symbol:
    - Collect sorted trading dates from PriceData
    - For each D in [start_day, end_day] that exists, for each horizon h:
      - target = (h)-th next trading session
      - If target exists: fwd_return = close[target]/close[D] - 1, upsert

    Missing dates / insufficient future data are skipped (no interpolation).
    """
    if horizons is None:
        horizons = [1, 5, 10]
    if not horizons:
        return {
            "start_day": str(start_day),
            "end_day": str(end_day),
            "rows_upserted": 0,
            "symbols_seen": 0,
        }

    max_h = max(horizons)
    # Buffer to fetch enough future data (account for weekends/holidays)
    buf_end = end_day + timedelta(days=max_h * 3)

    price_repo = PriceDataRepository(db)
    label_repo = PriceLabelRepository(db)

    rows = price_repo.list_in_date_range(start_day, buf_end)

    # symbol -> date -> close
    by_symbol: dict[str, dict[date, float]] = defaultdict(dict)
    for p in rows:
        by_symbol[p.stock_symbol][p.date] = float(p.close)

    rows_upserted = 0
    for symbol, date_to_close in by_symbol.items():
        dates = sorted(date_to_close.keys())
        idx = {d: i for i, d in enumerate(dates)}
        for d in dates:
            if d < start_day or d > end_day:
                continue
            close_d = date_to_close.get(d)
            if close_d is None or close_d == 0:
                continue
            for h in horizons:
                i = idx.get(d)
                if i is None:
                    continue
                j = i + h
                if j >= len(dates):
                    continue
                target = dates[j]
                close_target = date_to_close.get(target)
                if close_target is None or close_target == 0:
                    continue
                fwd_return = (close_target / close_d) - 1.0
                label_repo.upsert(symbol, d, h, fwd_return)
                rows_upserted += 1

    symbols_seen = len(by_symbol)
    logger.info(
        "Forward returns: start=%s end=%s horizons=%s rows_upserted=%s symbols=%s",
        start_day,
        end_day,
        horizons,
        rows_upserted,
        symbols_seen,
    )
    return {
        "start_day": str(start_day),
        "end_day": str(end_day),
        "rows_upserted": rows_upserted,
        "symbols_seen": symbols_seen,
    }
