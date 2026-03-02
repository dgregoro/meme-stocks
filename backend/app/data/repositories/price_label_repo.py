from __future__ import annotations

from datetime import date
from typing import Sequence

from sqlalchemy import and_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.price_labels import PriceLabel
from backend.app.utils.errors import DataAccessError


class PriceLabelRepository:
    """Data access layer for PriceLabel forward-return labels."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(
        self,
        symbol: str,
        trading_day: date,
        horizon_days: int,
        fwd_return: float,
    ) -> None:
        """Insert or update a label for (symbol, trading_day, horizon_days).

        Caller is responsible for committing the transaction.
        """
        try:
            existing = self.get(symbol, trading_day, horizon_days)
            if existing is None:
                label = PriceLabel(
                    symbol=symbol,
                    trading_day=trading_day,
                    horizon_days=horizon_days,
                    fwd_return=fwd_return,
                )
                self._session.add(label)
            else:
                existing.fwd_return = fwd_return
            self._session.flush()
        except SQLAlchemyError as exc:  # pragma: no cover - defensive
            raise DataAccessError(
                f"Failed to upsert price label for {symbol} @ {trading_day} h={horizon_days}"
            ) from exc

    def get(self, symbol: str, trading_day: date, horizon_days: int) -> PriceLabel | None:
        """Fetch a single label row or None if not found."""
        stmt = select(PriceLabel).where(
            and_(
                PriceLabel.symbol == symbol,
                PriceLabel.trading_day == trading_day,
                PriceLabel.horizon_days == horizon_days,
            )
        )
        try:
            return self._session.execute(stmt).scalar_one_or_none()
        except SQLAlchemyError as exc:  # pragma: no cover - defensive
            raise DataAccessError("Failed to fetch price label") from exc

    def list_for_symbol(
        self,
        symbol: str,
        start_day: date,
        end_day: date,
        horizon_days: int,
    ) -> Sequence[PriceLabel]:
        """List labels for a symbol and horizon in [start_day, end_day], ordered by trading_day."""
        stmt = (
            select(PriceLabel)
            .where(
                and_(
                    PriceLabel.symbol == symbol,
                    PriceLabel.trading_day >= start_day,
                    PriceLabel.trading_day <= end_day,
                    PriceLabel.horizon_days == horizon_days,
                )
            )
            .order_by(PriceLabel.trading_day.asc())
        )
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover - defensive
            raise DataAccessError(f"Failed to list price labels for {symbol}") from exc
