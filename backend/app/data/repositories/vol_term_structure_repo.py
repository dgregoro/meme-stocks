"""Persistence for VIX / VIX3M term-structure observations."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.vol_term_structure_observation import VolTermStructureObservation


class VolTermStructureRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_for_date(self, observation_date: dt.date) -> VolTermStructureObservation | None:
        return self._db.scalar(
            select(VolTermStructureObservation).where(VolTermStructureObservation.observation_date == observation_date)
        )

    def list_between(self, start: dt.date, end: dt.date) -> list[VolTermStructureObservation]:
        rows = self._db.scalars(
            select(VolTermStructureObservation)
            .where(
                VolTermStructureObservation.observation_date >= start,
                VolTermStructureObservation.observation_date <= end,
            )
            .order_by(VolTermStructureObservation.observation_date.asc())
        ).all()
        return list(rows)

    def upsert_row(
        self,
        observation_date: dt.date,
        vix_close: float,
        vix3m_close: float,
    ) -> VolTermStructureObservation:
        row = self.get_for_date(observation_date)
        if row is None:
            row = VolTermStructureObservation(
                observation_date=observation_date,
                vix_close=vix_close,
                vix3m_close=vix3m_close,
            )
            self._db.add(row)
        else:
            row.vix_close = vix_close
            row.vix3m_close = vix3m_close
        return row

    def delete_between(self, start: dt.date, end: dt.date) -> int:
        to_del = self.list_between(start, end)
        n = len(to_del)
        for r in to_del:
            self._db.delete(r)
        return n
