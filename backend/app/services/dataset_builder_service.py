"""Build research dataset by joining price_labels with same-day OHLCV.

Legacy datasets included Reddit daily features; those columns are kept as zeros
so downstream experiment CLIs and CSV schemas stay compatible.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import subprocess  # nosec B404
from datetime import date, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from sqlalchemy import Integer, Float, and_, cast, literal, select
from sqlalchemy.orm import Session

from backend.app.models.price_data import PriceData
from backend.app.models.price_labels import PriceLabel

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)


def _get_git_sha() -> str | None:
    """Return short git SHA if available, else None."""
    import shutil  # noqa: PLC0415

    git_path = shutil.which("git")
    if not git_path:
        return os.environ.get("GIT_SHA")
    try:
        result = subprocess.run(  # nosec B603, B607
            [git_path, "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=Path(__file__).resolve().parents[3],
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return os.environ.get("GIT_SHA")


def build_training_dataset(
    db: Session,
    start_day: date,
    end_day: date,
    *,
    horizon_days: int = 5,
    symbols: list[str] | None = None,
    output_path: str,
    format: Literal["csv", "parquet"] = "csv",
    dataset_version: str | None = None,
) -> dict[str, int | str]:
    """Join price_labels and PriceData; write deterministic snapshot.

    INNER JOIN path: labels for (symbol, trading_day, horizon_days) with optional
    same-day PriceData for close/volume. Reddit aggregate columns are zeros.

    Output columns unchanged from the Reddit era for experiment compatibility.
    """
    if dataset_version is None:
        git_sha = _get_git_sha()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        dataset_version = f"{git_sha or 'nogit'}_{today}"

    label_attr = f"y_fwd_return_{horizon_days}"
    stmt = (
        select(
            PriceLabel.symbol,
            PriceLabel.trading_day,
            cast(literal(0), Integer).label("mention_count"),
            cast(literal(0), Integer).label("unique_authors"),
            cast(literal(0), Integer).label("total_upvotes"),
            cast(literal(0), Integer).label("total_comments"),
            cast(literal(0.0), Float).label("upvote_weighted_mentions"),
            PriceData.close,
            PriceData.volume,
            PriceLabel.fwd_return.label(label_attr),
        )
        .outerjoin(
            PriceData,
            and_(
                PriceLabel.symbol == PriceData.stock_symbol,
                PriceLabel.trading_day == PriceData.date,
            ),
        )
        .where(
            PriceLabel.trading_day >= start_day,
            PriceLabel.trading_day <= end_day,
            PriceLabel.horizon_days == horizon_days,
        )
        .order_by(PriceLabel.trading_day.asc(), PriceLabel.symbol.asc())
    )
    if symbols:
        stmt = stmt.where(PriceLabel.symbol.in_(symbols))

    rows = list(db.execute(stmt).all())

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
        label_attr,
    ]

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    metadata = {
        "start_day": str(start_day),
        "end_day": str(end_day),
        "horizon_days": horizon_days,
        "symbols_filter": symbols,
        "git_sha": _get_git_sha(),
        "generation_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_version": dataset_version,
        "source": "price_labels_only",
    }
    metadata_path = out.with_suffix(out.suffix + ".meta.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    if format.lower() == "parquet":
        _write_parquet(headers, rows, label_attr, str(out))
    else:
        _write_csv(headers, rows, label_attr, str(out))

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
        "dataset_version": dataset_version,
        "metadata_path": str(metadata_path),
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
