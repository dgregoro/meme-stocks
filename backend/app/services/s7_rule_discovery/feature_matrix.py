"""S7: build deterministic daily feature + forward-label rows from ``price_data``."""

from __future__ import annotations

import csv
import logging
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.services.daily_frequency_strategy_research import (
    DailyBar,
    bars_from_price_rows,
    realized_vol_series,
    volume_log_z_series,
)

logger = logging.getLogger(__name__)


def forward_pct_from_bars(bars: list[DailyBar], i: int, h: int) -> float | None:
    if h < 1 or i + h >= len(bars):
        return None
    c0, c1 = bars[i].close, bars[i + h].close
    if c0 <= 0:
        return None
    return (c1 / c0 - 1.0) * 100.0


def ret_1d_pct(bars: list[DailyBar], i: int) -> float | None:
    if i < 1:
        return None
    c0, c1 = bars[i - 1].close, bars[i].close
    if c0 <= 0:
        return None
    return (c1 / c0 - 1.0) * 100.0


def build_feature_matrix_rows(
    db: Session,
    symbol: str,
    start: date,
    end: date,
    horizon: int,
) -> tuple[list[dict[str, Any]], str]:
    """Return rows with features + forward return label; second value is label column name.

    Uses full history through ``end`` so rolling windows are warm before ``start``.
    """
    if start > end:
        raise ValueError("start must be on or before end")
    if horizon < 1:
        raise ValueError("horizon must be >= 1")

    settings = get_settings()
    rv_w = max(2, int(settings.daily_strategy_realized_vol_window))
    vz_w = max(2, int(settings.daily_strategy_volume_z_window))
    symu = symbol.strip().upper()
    repo = PriceDataRepository(db)
    rows_orm = repo.list_for_stock(symu)
    bars_all = bars_from_price_rows(rows_orm)
    bars = [b for b in bars_all if b.d <= end]
    min_need = max(rv_w, vz_w) + horizon + 3
    if len(bars) < min_need:
        raise ValueError(
            f"{symu}: insufficient price bars through {end} for "
            f"S7 matrix (have {len(bars)}, need ~{min_need} for vol/z windows and horizon {horizon})"
        )

    closes = [b.close for b in bars]
    vols = [b.volume for b in bars]
    rvs = realized_vol_series(closes, rv_w)
    vzs = volume_log_z_series(vols, vz_w)
    label_col = f"fwd_{horizon}_pct"
    out: list[dict[str, Any]] = []
    for i, b in enumerate(bars):
        if b.d < start or b.d > end:
            continue
        fwd = forward_pct_from_bars(bars, i, horizon)
        if fwd is None:
            continue
        r1 = ret_1d_pct(bars, i)
        rv_i = rvs[i]
        vz_i = vzs[i]
        out.append(
            {
                "date": b.d,
                "symbol": symu,
                "ret_1d_pct": round(r1, 6) if r1 is not None else None,
                "rv_w": round(rv_i, 8) if rv_i is not None else None,
                "vol_z_w": round(vz_i, 6) if vz_i is not None else None,
                label_col: round(fwd, 6),
            }
        )
    if not out:
        raise ValueError(f"{symu}: no evaluable rows in [{start},{end}] with horizon {horizon}")
    logger.info(
        "S7 matrix: symbol=%s rows=%s label=%s window_rv=%s window_vz=%s",
        symu,
        len(out),
        label_col,
        rv_w,
        vz_w,
    )
    return out, label_col


def write_matrix_csv(path: Path, rows: list[dict[str, Any]], label_col: str) -> None:
    """Write matrix CSV; creates parent directories."""
    fieldnames = ["date", "symbol", "ret_1d_pct", "rv_w", "vol_z_w", label_col]
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            row_out: dict[str, Any] = {}
            for k in fieldnames:
                v = r.get(k)
                if k == "date" and isinstance(v, date):
                    row_out[k] = v.isoformat()
                elif v is None:
                    row_out[k] = ""
                else:
                    row_out[k] = v
            w.writerow(row_out)
