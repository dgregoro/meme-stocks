"""Tests for vol_term_structure_observations repository."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import backend.app.cli.orm_imports  # noqa: F401
from backend.app.data.database import Base
from backend.app.data.repositories.vol_term_structure_repo import VolTermStructureRepository


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
def test_vol_term_repo_upsert_updates_row() -> None:
    db = _session()
    try:
        repo = VolTermStructureRepository(db)
        repo.upsert_row(date(2024, 1, 2), 18.0, 19.0)
        db.commit()
        repo.upsert_row(date(2024, 1, 2), 18.5, 19.2)
        db.commit()
        rows = repo.list_between(date(2024, 1, 1), date(2024, 1, 3))
        assert len(rows) == 1
        assert rows[0].vix_close == pytest.approx(18.5)
        assert rows[0].vix3m_close == pytest.approx(19.2)
    finally:
        db.close()
