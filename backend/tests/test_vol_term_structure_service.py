"""Tests for Yahoo-backed vol-term backfill service (mocked client)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import backend.app.cli.orm_imports  # noqa: F401
from backend.app.data.database import Base
from backend.app.data.repositories.vol_term_structure_repo import VolTermStructureRepository
from backend.app.services.vol_term_structure_service import backfill_vol_term_observations


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


@pytest.mark.unit
def test_backfill_vol_term_observations_uses_client_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("S3_VIX_SYMBOL", "^VIX")
    monkeypatch.setenv("S3_VIX3M_SYMBOL", "^VIX3M")
    from backend.app.config import get_settings

    get_settings.cache_clear()
    db = _session()
    try:
        client = MagicMock()
        client.fetch_vix_vix3m_closes.return_value = [
            (date(2024, 1, 2), 18.0, 19.0),
            (date(2024, 1, 3), 18.1, 19.1),
        ]
        out = backfill_vol_term_observations(db, date(2024, 1, 2), date(2024, 1, 3), client=client)
        assert out["rows_upserted"] == 2
        repo = VolTermStructureRepository(db)
        rows = repo.list_between(date(2024, 1, 1), date(2024, 1, 10))
        assert len(rows) == 2
    finally:
        db.close()
        get_settings.cache_clear()
