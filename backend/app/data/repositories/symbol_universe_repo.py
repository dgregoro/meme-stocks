from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.symbol_universe import SymbolUniverse
from backend.app.utils.errors import DataAccessError


class SymbolUniverseRepository:
    """Repository for SymbolUniverse entities."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, symbol: str) -> SymbolUniverse | None:
        """Get a symbol from the universe by symbol."""
        try:
            stmt = select(SymbolUniverse).where(SymbolUniverse.symbol == symbol.upper())
            return self._session.execute(stmt).scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise DataAccessError(f"Failed to get symbol {symbol}") from exc

    def add(self, symbol: SymbolUniverse) -> None:
        """Add a symbol to the universe."""
        try:
            self._session.add(symbol)
            self._session.flush()
        except SQLAlchemyError as exc:
            raise DataAccessError(f"Failed to add symbol {symbol.symbol}") from exc

    def upsert(self, symbol: SymbolUniverse) -> None:
        """Insert or update a symbol in the universe."""
        try:
            existing = self.get(symbol.symbol)
            if existing:
                # Update existing record
                existing.name = symbol.name
                existing.exchange = symbol.exchange
                existing.is_etf = symbol.is_etf
                existing.is_active = symbol.is_active
                existing.sector = symbol.sector
                existing.industry = symbol.industry
                existing.last_seen = symbol.last_seen or datetime.now(timezone.utc)
                existing.updated_at = datetime.now(timezone.utc)
            else:
                # Insert new record
                symbol.last_seen = symbol.last_seen or datetime.now(timezone.utc)
                self._session.add(symbol)
            self._session.flush()
        except SQLAlchemyError as exc:
            raise DataAccessError(f"Failed to upsert symbol {symbol.symbol}") from exc

    def list_all(self, active_only: bool = True) -> Sequence[SymbolUniverse]:
        """List all symbols in the universe."""
        try:
            stmt = select(SymbolUniverse)
            if active_only:
                stmt = stmt.where(SymbolUniverse.is_active == True)  # noqa: E712
            stmt = stmt.order_by(SymbolUniverse.symbol)
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:
            raise DataAccessError("Failed to list symbols") from exc

    def get_symbols_set(self, active_only: bool = True) -> set[str]:
        """Get a set of all symbol strings (for fast lookup)."""
        try:
            symbols = self.list_all(active_only=active_only)
            return {s.symbol.upper() for s in symbols}
        except SQLAlchemyError as exc:
            raise DataAccessError("Failed to get symbols set") from exc

    def count(self, active_only: bool = True) -> int:
        """Count symbols in the universe."""
        try:
            stmt = select(SymbolUniverse)
            if active_only:
                stmt = stmt.where(SymbolUniverse.is_active == True)  # noqa: E712
            return len(list(self._session.execute(stmt).scalars().all()))
        except SQLAlchemyError as exc:
            raise DataAccessError("Failed to count symbols") from exc
