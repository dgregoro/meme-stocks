"""Tests for causal dataset builder."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from backend.app.services.causal_dataset_builder import (
    CausalDataset,
    InsufficientDataResult,
    build_dataset,
)


def _write_bars(root: Path, symbol: str, rows: list[tuple]) -> None:
    """Write parquet bars for tests."""
    if not rows:
        return
    table = pa.table(
        {
            "ts": pa.array([r[0] for r in rows], type=pa.timestamp("us", tz="UTC")),
            "o": pa.array([r[1] for r in rows], type=pa.float64()),
            "h": pa.array([r[1] for r in rows], type=pa.float64()),
            "l": pa.array([r[1] for r in rows], type=pa.float64()),
            "c": pa.array([r[1] for r in rows], type=pa.float64()),
            "v": pa.array([r[2] for r in rows], type=pa.float64()),
            "n": pa.array([0] * len(rows), type=pa.int64()),
            "vw": pa.array([0.0] * len(rows), type=pa.float64()),
            "source": pa.array(["test"] * len(rows), type=pa.string()),
        }
    )
    base = root / "bars" / f"symbol={symbol}" / "date=2026-01-15"
    base.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, base / "part.parquet")


def _post(
    collected_at: datetime,
    title: str = "buy moon",
    upvotes: int = 10,
    comments: int = 5,
    posted_at: datetime | None = None,
):
    attrs: dict = {
        "collected_at": collected_at,
        "title": title,
        "body": "",
        "upvotes": upvotes,
        "comments": comments,
    }
    if posted_at is not None:
        attrs["posted_at"] = posted_at
    return SimpleNamespace(**attrs)


@pytest.mark.unit
def test_build_dataset_insufficient_no_bars(tmp_path: Path) -> None:
    """Returns InsufficientDataResult when no price data."""
    result = build_dataset(
        "AAPL",
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 30, tzinfo=timezone.utc),
        "1h",
        posts=[],
        parquet_root=str(tmp_path),
    )
    assert isinstance(result, InsufficientDataResult)
    assert result.reason == "no_price_data"


@pytest.mark.unit
def test_build_dataset_insufficient_too_few_buckets(tmp_path: Path) -> None:
    """Returns InsufficientDataResult when buckets < min_required."""
    rows = [
        (
            datetime(2026, 1, 15, 9, i, tzinfo=timezone.utc),
            100.0 + i * 0.1,
            1000.0,
        )
        for i in range(10)
    ]
    _write_bars(tmp_path, "AAPL", rows)

    with patch("backend.app.services.causal_dataset_builder.get_settings") as mock:
        mock.return_value.causal_min_buckets_1h = 20

        result = build_dataset(
            "AAPL",
            datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
            datetime(2026, 1, 15, 18, 0, tzinfo=timezone.utc),
            "1h",
            posts=[],
            parquet_root=str(tmp_path),
        )
    assert isinstance(result, InsufficientDataResult)
    assert result.reason == "insufficient_buckets"


@pytest.mark.unit
def test_build_dataset_success(tmp_path: Path) -> None:
    """Builds aligned dataset with mentions and sentiment when enough data."""
    # Create 30 hourly bars (one per hour over 30 hours)
    base = datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)
    rows = [(base + timedelta(hours=h), 100.0 + h * 0.01, 1000.0) for h in range(30)]
    _write_bars(tmp_path, "AAPL", rows)

    post_ts = datetime(2026, 1, 1, 10, 15, tzinfo=timezone.utc)
    posts = [_post(post_ts, "buy moon gains")]

    with patch("backend.app.services.causal_dataset_builder.get_settings") as mock:
        mock.return_value.causal_min_buckets_1h = 10

        result = build_dataset(
            "AAPL",
            datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc),
            datetime(2026, 1, 3, 16, 0, tzinfo=timezone.utc),
            "1h",
            posts=posts,
            parquet_root=str(tmp_path),
        )

    assert isinstance(result, CausalDataset)
    assert result.symbol == "AAPL"
    assert result.freq == "1h"
    assert "mentions" in result.df.columns
    assert "sentiment_mean" in result.df.columns
    assert "price_close" in result.df.columns
    assert "returns" in result.df.columns
    assert result.sample_size >= 10
    assert result.df["mentions"].sum() >= 1


@pytest.mark.unit
def test_build_dataset_no_lookahead(tmp_path: Path) -> None:
    """Posts outside the window are excluded."""
    rows = []
    for d in range(90):
        base = datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)
        month = 1 + d // 28
        day = 1 + (d % 28)
        try:
            t = base.replace(month=month, day=day)
        except ValueError:
            t = base.replace(month=min(month, 12), day=min(day, 28))
        rows.append((t, 100.0, 1000.0))
    _write_bars(tmp_path, "AAPL", rows)

    posts = [_post(datetime(2025, 12, 31, 10, 0, tzinfo=timezone.utc), "buy")]

    with patch("backend.app.services.causal_dataset_builder.get_settings") as mock:
        mock.return_value.causal_min_buckets_1d = 10

        result = build_dataset(
            "AAPL",
            datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 3, 30, 23, 59, tzinfo=timezone.utc),
            "1d",
            posts=posts,
            parquet_root=str(tmp_path),
        )

    if isinstance(result, CausalDataset):
        assert result.df["mentions"].sum() == 0


@pytest.mark.unit
def test_build_dataset_buckets_by_posted_at(tmp_path: Path) -> None:
    """Posts with same collected_at but different posted_at land in buckets by posted_at."""
    base = datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc)
    rows = [(base + timedelta(hours=h), 100.0 + h * 0.01, 1000.0) for h in range(30)]
    _write_bars(tmp_path, "GME", rows)

    collected_late = datetime(2026, 1, 15, 14, 0, tzinfo=timezone.utc)
    post_a = _post(
        collected_at=collected_late,
        title="GME moon",
        posted_at=datetime(2026, 1, 15, 10, 15, tzinfo=timezone.utc),
    )
    post_b = _post(
        collected_at=collected_late,
        title="GME buy",
        posted_at=datetime(2026, 1, 15, 11, 15, tzinfo=timezone.utc),
    )

    with patch("backend.app.services.causal_dataset_builder.get_settings") as mock:
        mock.return_value.causal_min_buckets_1h = 10

        result = build_dataset(
            "GME",
            datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
            datetime(2026, 1, 16, 18, 0, tzinfo=timezone.utc),
            "1h",
            posts=[post_a, post_b],
            parquet_root=str(tmp_path),
        )

    assert isinstance(result, CausalDataset)
    df = result.df.copy()
    df["bucket_hour"] = df.index.hour
    mentions_by_hour = df.groupby("bucket_hour")["mentions"].sum()
    assert mentions_by_hour.get(10, 0) == 1, "Posted at 10:15 should land in 10:00 bucket"
    assert mentions_by_hour.get(11, 0) == 1, "Posted at 11:15 should land in 11:00 bucket"
    assert mentions_by_hour.get(14, 0) == 0, "Collected at 14:00 should not determine bucket"
