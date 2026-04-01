"""Tests for S7 rule-discovery matrix + quantile grid."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import backend.app.cli.orm_imports  # noqa: F401
from backend.app.config import get_settings
from backend.app.data.database import Base
from backend.app.models.price_data import PriceData
from backend.app.models.stock import Stock
from backend.app.services.s7_rule_discovery.feature_matrix import build_feature_matrix_rows, write_matrix_csv
from backend.app.services.s7_rule_discovery.grid_search import (
    load_matrix_csv,
    run_quantile_rule_grid,
    run_search_from_matrix_path,
)


def _session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _seed_bars(db: Session, symbol: str, start: date, n: int) -> None:
    db.add(Stock(symbol=symbol, name=symbol, sector=None, market_cap=None))
    for i in range(n):
        d = start + timedelta(days=i)
        c = 100.0 + 0.2 * i + (0.5 * i % 3)
        db.add(
            PriceData(
                stock_symbol=symbol,
                date=d,
                open=c,
                high=c + 0.5,
                low=c - 0.5,
                close=c,
                volume=900_000 + i * 1500,
            )
        )


@pytest.mark.unit
def test_run_quantile_rule_grid_requires_ack() -> None:
    rows = [
        {"date": date(2020, 1, 2), "symbol": "X", "rv_w": 0.01, "fwd_5_pct": 0.1},
    ]
    with pytest.raises(ValueError, match="ack_overfitting"):
        run_quantile_rule_grid(rows, train_end=date(2020, 1, 1), label_key="fwd_5_pct", ack_overfitting_risk=False)


@pytest.mark.unit
def test_run_quantile_rule_grid_train_test_split(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("S7_RULE_DISCOVERY_N_QUANTILES", "4")
    monkeypatch.setenv("S7_RULE_DISCOVERY_MAX_RULES", "500")
    get_settings.cache_clear()
    try:
        rows: list[dict] = []
        d0 = date(2020, 1, 2)
        for i in range(80):
            d = d0 + timedelta(days=i)
            rv = 0.01 + (i % 10) * 0.0001
            # trend in label post-split for high rv
            y = -0.05 if i < 40 else (0.3 if rv > 0.0105 else -0.02)
            rows.append(
                {
                    "date": d,
                    "symbol": "Z",
                    "rv_w": rv,
                    "vol_z_w": 0.0,
                    "fwd_5_pct": y,
                }
            )
        out = run_quantile_rule_grid(
            rows,
            train_end=date(2020, 2, 15),
            label_key="fwd_5_pct",
            ack_overfitting_risk=True,
        )
        assert out["kind"] == "s7_rule_discovery_search"
        assert out["n_rules_evaluated"] >= 1
        assert "research_envelope" in out
        assert out["research_envelope"]["run_kind"] == "s7_rule_discovery_search"
        assert any((r.get("test_n_signal") or 0) > 0 for r in out["rule_results"])
    finally:
        get_settings.cache_clear()


@pytest.mark.unit
def test_load_matrix_csv_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "m.csv"
    p.write_text(
        "date,symbol,ret_1d_pct,rv_w,vol_z_w,fwd_1_pct\n"
        "2020-01-02,AB,0.1,0.02,0.5,0.2\n"
        "2020-01-03,AB,0.2,0.03,0.6,-0.1\n",
        encoding="utf-8",
    )
    rows, lab = load_matrix_csv(p)
    assert lab == "fwd_1_pct"
    assert len(rows) == 2
    assert rows[0]["date"] == date(2020, 1, 2)


@pytest.mark.unit
def test_run_search_from_matrix_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("S7_RULE_DISCOVERY_N_QUANTILES", "4")
    monkeypatch.setenv("S7_RULE_DISCOVERY_MAX_RULES", "200")
    get_settings.cache_clear()
    try:
        p = tmp_path / "m.csv"
        lines = ["date,symbol,ret_1d_pct,rv_w,vol_z_w,fwd_1_pct"]
        d0 = date(2019, 6, 1)
        for i in range(60):
            d = d0 + timedelta(days=i)
            lines.append(f"{d.isoformat()},Q,0.01,0.0{2 + (i % 5)},0.1,{0.01 * (i % 3)}")
        p.write_text("\n".join(lines), encoding="utf-8")
        out = run_search_from_matrix_path(p, train_end=date(2019, 7, 15), label_key=None, ack_overfitting_risk=True)
        assert out["test_rows"] >= 10
    finally:
        get_settings.cache_clear()


@pytest.mark.unit
def test_build_feature_matrix_rows_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_REALIZED_VOL_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_VOLUME_Z_WINDOW", "5")
    get_settings.cache_clear()
    db = _session()
    try:
        _seed_bars(db, "S7X", date(2024, 1, 2), 80)
        db.commit()
        rows, label = build_feature_matrix_rows(db, "S7X", date(2024, 2, 1), date(2024, 4, 1), horizon=3)
        assert label == "fwd_3_pct"
        assert len(rows) >= 20
        assert all(label in r for r in rows)
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_write_matrix_csv(tmp_path: Path) -> None:
    p = tmp_path / "out.csv"
    write_matrix_csv(
        p,
        [
            {
                "date": date(2020, 1, 2),
                "symbol": "ZZ",
                "ret_1d_pct": 0.1,
                "rv_w": None,
                "vol_z_w": 1.0,
                "fwd_2_pct": 0.2,
            }
        ],
        "fwd_2_pct",
    )
    text = p.read_text(encoding="utf-8")
    assert "fwd_2_pct" in text
