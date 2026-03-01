"""Repository for intraday ingestion state and run tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.intraday_ingest_run import IntradayIngestRun
from backend.app.models.intraday_ingest_state import IntradayIngestState
from backend.app.utils.errors import DataAccessError


class IntradayIngestRepository:
    """Data access for intraday ingest state and runs."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def ensure_symbols(self, symbols: list[str]) -> None:
        """Insert missing symbols with default state. Caller commits."""
        for symbol in symbols:
            stmt = select(IntradayIngestState).where(IntradayIngestState.symbol == symbol)
            try:
                existing = self._session.execute(stmt).scalar_one_or_none()
                if existing is None:
                    self._session.add(
                        IntradayIngestState(
                            symbol=symbol,
                            last_ts=None,
                            status="active",
                            error_count=0,
                            last_error=None,
                        )
                    )
            except SQLAlchemyError as exc:
                raise DataAccessError(f"Failed to ensure symbol {symbol}") from exc

    def get_states(self, symbols: list[str]) -> dict[str, IntradayIngestState]:
        """Return state rows keyed by symbol. Missing symbols are absent from the dict."""
        if not symbols:
            return {}
        stmt = select(IntradayIngestState).where(IntradayIngestState.symbol.in_(symbols))
        try:
            rows = self._session.execute(stmt).scalars().all()
            return {r.symbol: r for r in rows}
        except SQLAlchemyError as exc:
            raise DataAccessError("Failed to get ingest states") from exc

    def update_success(self, symbol: str, last_ts: datetime) -> None:
        """Update last_ts and clear error state for symbol. Caller commits."""
        stmt = select(IntradayIngestState).where(IntradayIngestState.symbol == symbol)
        try:
            row = self._session.execute(stmt).scalar_one_or_none()
            if row:
                row.last_ts = last_ts
                row.status = "active"
                row.error_count = 0
                row.last_error = None
                row.updated_at = datetime.now(timezone.utc)
        except SQLAlchemyError as exc:
            raise DataAccessError(f"Failed to update success for {symbol}") from exc

    def mark_error(self, symbol: str, error: str) -> None:
        """Increment error_count and set last_error. Caller commits."""
        stmt = select(IntradayIngestState).where(IntradayIngestState.symbol == symbol)
        try:
            row = self._session.execute(stmt).scalar_one_or_none()
            if row:
                row.error_count = (row.error_count or 0) + 1
                row.last_error = error[:2000] if len(error) > 2000 else error
                row.status = "error"
                row.updated_at = datetime.now(timezone.utc)
        except SQLAlchemyError as exc:
            raise DataAccessError(f"Failed to mark error for {symbol}") from exc

    def pause(self, symbol: str) -> None:
        """Set status to paused. Caller commits."""
        stmt = select(IntradayIngestState).where(IntradayIngestState.symbol == symbol)
        try:
            row = self._session.execute(stmt).scalar_one_or_none()
            if row:
                row.status = "paused"
                row.updated_at = datetime.now(timezone.utc)
        except SQLAlchemyError as exc:
            raise DataAccessError(f"Failed to pause {symbol}") from exc

    def resume(self, symbol: str) -> None:
        """Set status to active. Caller commits."""
        stmt = select(IntradayIngestState).where(IntradayIngestState.symbol == symbol)
        try:
            row = self._session.execute(stmt).scalar_one_or_none()
            if row:
                row.status = "active"
                row.updated_at = datetime.now(timezone.utc)
        except SQLAlchemyError as exc:
            raise DataAccessError(f"Failed to resume {symbol}") from exc

    def create_run(self, symbols_count: int, notes: str | None = None) -> IntradayIngestRun:
        """Create a new run record; returns it. Caller commits."""
        run = IntradayIngestRun(
            started_at=datetime.now(timezone.utc),
            ended_at=None,
            symbols_count=symbols_count,
            bars_written=0,
            errors_count=0,
            notes=notes,
        )
        try:
            self._session.add(run)
            self._session.flush()
            return run
        except SQLAlchemyError as exc:
            raise DataAccessError("Failed to create intraday run") from exc

    def finish_run(
        self,
        run_id: int,
        bars_written: int = 0,
        errors_count: int = 0,
        notes: str | None = None,
    ) -> None:
        """Set ended_at and optional counts/notes. Caller commits."""
        stmt = select(IntradayIngestRun).where(IntradayIngestRun.id == run_id)
        try:
            run = self._session.execute(stmt).scalar_one_or_none()
            if run:
                run.ended_at = datetime.now(timezone.utc)
                run.bars_written = bars_written
                run.errors_count = errors_count
                if notes is not None:
                    run.notes = notes
        except SQLAlchemyError as exc:
            raise DataAccessError(f"Failed to finish run {run_id}") from exc

    def get_latest_run(self) -> IntradayIngestRun | None:
        """Return the most recent run by started_at, or None."""
        stmt = (
            select(IntradayIngestRun)
            .order_by(IntradayIngestRun.started_at.desc())
            .limit(1)
        )
        try:
            return self._session.execute(stmt).scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise DataAccessError("Failed to get latest intraday run") from exc

    def count_by_status(self) -> dict[str, int]:
        """Return counts of symbols per status (active, paused, error)."""
        from sqlalchemy import func

        stmt = select(IntradayIngestState.status, func.count(IntradayIngestState.symbol)).group_by(
            IntradayIngestState.status
        )
        try:
            rows = self._session.execute(stmt).all()
            return {row[0]: row[1] for row in rows}
        except SQLAlchemyError as exc:
            raise DataAccessError("Failed to count by status") from exc

    def get_newest_last_ts(self) -> datetime | None:
        """Return the newest last_ts across all symbols, or None."""
        from sqlalchemy import func

        stmt = select(func.max(IntradayIngestState.last_ts)).where(
            IntradayIngestState.last_ts.isnot(None)
        )
        try:
            return self._session.execute(stmt).scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise DataAccessError("Failed to get newest last_ts") from exc

    def get_oldest_last_ts(self) -> datetime | None:
        """Return the oldest last_ts across all symbols (laggards), or None."""
        from sqlalchemy import func

        stmt = select(func.min(IntradayIngestState.last_ts)).where(
            IntradayIngestState.last_ts.isnot(None)
        )
        try:
            return self._session.execute(stmt).scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise DataAccessError("Failed to get oldest last_ts") from exc
