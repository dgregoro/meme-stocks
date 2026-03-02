"""Build training dataset by joining reddit_daily_features and price_labels."""

from __future__ import annotations

import csv
import logging
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from backend.app.models.price_data import PriceData
from backend.app.models.price_labels import PriceLabel
from backend.app.models.reddit_daily_feature import RedditDailyFeature

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)


def build_training_dataset(
    db: Session,
    start_day: date,
    end_day: date,
    *,
    horizon_days: int = 5,
    symbols: list[str] | None = None,
    output_path: str,
    format: str = "csv",
) -> dict[str, int | str]:
    """Join reddit_daily_features and price_labels; write deterministic snapshot.

    INNER JOIN on (symbol, trading_day): only rows with both features and label.
    Features use data as-of end of day D; label uses close[D+h]/close[D]-1 (no look-ahead).

    Output columns: symbol, trading_day, mention_count, unique_authors, total_upvotes,
    total_comments, upvote_weighted_mentions, close, volume, y_fwd_return_{horizon_days}

    Sorted by trading_day asc, symbol asc.
    """
    # Build join: RedditDailyFeature INNER JOIN PriceLabel ON (symbol, trading_day) AND horizon_days
    # Optional LEFT JOIN PriceData for same-day close, volume
    stmt = (
        select(
            RedditDailyFeature.symbol,
            RedditDailyFeature.trading_day,
            RedditDailyFeature.mention_count,
            RedditDailyFeature.unique_authors,
            RedditDailyFeature.total_upvotes,
            RedditDailyFeature.total_comments,
            RedditDailyFeature.upvote_weighted_mentions,
            PriceData.close,
            PriceData.volume,
            PriceLabel.fwd_return.label(f"y_fwd_return_{horizon_days}"),
        )
        .join(
            PriceLabel,
            and_(
                RedditDailyFeature.symbol == PriceLabel.symbol,
                RedditDailyFeature.trading_day == PriceLabel.trading_day,
                PriceLabel.horizon_days == horizon_days,
            ),
        )
        .outerjoin(
            PriceData,
            and_(
                RedditDailyFeature.symbol == PriceData.stock_symbol,
                RedditDailyFeature.trading_day == PriceData.date,
            ),
        )
        .where(
            RedditDailyFeature.trading_day >= start_day,
            RedditDailyFeature.trading_day <= end_day,
        )
        .order_by(RedditDailyFeature.trading_day.asc(), RedditDailyFeature.symbol.asc())
    )
    if symbols:
        stmt = stmt.where(RedditDailyFeature.symbol.in_(symbols))

    rows = list(db.execute(stmt).all())

    label_col = f"y_fwd_return_{horizon_days}"
    headers = [
        "symbol",
        "trading_day",
        "mention_count",
        "unique_authors",
        "total_upvotes",
        "total_comments",
        "upvote_weighted_mentions",
        "close",
        "volume",
        label_col,
    ]

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if format.lower() == "parquet":
        _write_parquet(headers, rows, label_col, str(out))
    else:
        _write_csv(headers, rows, label_col, str(out))

    logger.info(
        "Dataset built: start=%s end=%s horizon=%s rows=%s path=%s",
        start_day,
        end_day,
        horizon_days,
        len(rows),
        output_path,
    )
    return {
        "start_day": str(start_day),
        "end_day": str(end_day),
        "horizon_days": horizon_days,
        "rows_written": len(rows),
        "output_path": output_path,
    }


def _row_to_tuple(row: Any, label_col: str) -> tuple:
    return (
        row.symbol,
        str(row.trading_day),
        row.mention_count,
        row.unique_authors,
        row.total_upvotes,
        row.total_comments,
        row.upvote_weighted_mentions,
        row.close if row.close is not None else "",
        row.volume if row.volume is not None else "",
        getattr(row, label_col),
    )


def _write_csv(headers: list[str], rows: Sequence, label_col: str, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for row in rows:
            w.writerow(_row_to_tuple(row, label_col))


def _write_parquet(headers: list[str], rows: Sequence, label_col: str, path: str) -> None:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("pyarrow is required for parquet output. pip install pyarrow") from exc

    cols: dict[str, list[Any]] = {h: [] for h in headers}
    for row in rows:
        t = _row_to_tuple(row, label_col)
        for i, h in enumerate(headers):
            cols[h].append(t[i])

    def to_float(v: Any) -> float | None:
        if v is None or v == "":
            return None
        try:
            return float(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

    def to_int(v: Any) -> int | None:
        if v is None or v == "":
            return None
        try:
            return int(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

    arrays = []
    for h in headers:
        if h in ("symbol", "trading_day"):
            arrays.append(pa.array([str(x) if x is not None else "" for x in cols[h]], type=pa.string()))
        elif h in ("mention_count", "unique_authors", "total_upvotes", "total_comments"):
            arrays.append(pa.array([to_int(x) for x in cols[h]], type=pa.int64()))
        elif h == "volume":
            arrays.append(pa.array([to_int(x) for x in cols[h]], type=pa.int64()))
        else:
            arrays.append(pa.array([to_float(x) for x in cols[h]], type=pa.float64()))
    table = pa.table(dict(zip(headers, arrays)))
    pq.write_table(table, path)
