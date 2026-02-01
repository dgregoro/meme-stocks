"""API endpoints for symbol universe management."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.data.database import get_session
from backend.app.services.symbol_universe_service import SymbolUniverseService
from backend.app.utils.api_errors import error_detail
from backend.app.utils.errors import ExternalAPIError
from backend.app.utils.ticker_extractor import clear_symbol_universe_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/symbol-universe", tags=["symbol-universe"])


class RefreshResponse(BaseModel):
    """Response model for symbol universe refresh."""

    status: str
    inserted: int
    updated: int
    total: int
    errors: list[str]


class UniverseStatsResponse(BaseModel):
    """Response model for symbol universe statistics."""

    total_symbols: int
    active_symbols: int


@router.post("/refresh", response_model=RefreshResponse)
def refresh_symbol_universe(db: Session = Depends(get_session)) -> RefreshResponse:
    """Refresh the symbol universe from NASDAQ/SEC sources.

    This endpoint fetches stock listings from SEC EDGAR and updates the
    symbol universe database. The symbol universe is used to validate
    ticker symbols extracted from Reddit posts.

    Returns:
        Statistics about the refresh operation.
    """
    try:
        service = SymbolUniverseService(db)
        stats = service.refresh_from_nasdaq()

        # Clear cache so next ticker extraction uses updated universe
        clear_symbol_universe_cache()

        return RefreshResponse(
            status="success",
            inserted=stats.get("inserted", 0),
            updated=stats.get("updated", 0),
            total=stats.get("total", 0),
            errors=stats.get("errors", []),
        )
    except ExternalAPIError as exc:
        logger.error(f"External API error refreshing symbol universe: {exc}")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Error refreshing symbol universe: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to refresh symbol universe: {exc}") from exc


@router.get("/stats", response_model=UniverseStatsResponse)
def get_universe_stats(db: Session = Depends(get_session)) -> UniverseStatsResponse:
    """Get statistics about the symbol universe.

    Returns:
        Total and active symbol counts.
    """
    try:
        service = SymbolUniverseService(db)
        total = service.count(active_only=False)
        active = service.count(active_only=True)

        return UniverseStatsResponse(total_symbols=total, active_symbols=active)
    except Exception as exc:
        logger.error(f"Error getting universe stats: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("InternalServerError", f"Failed to get universe stats: {exc}"),
        ) from exc
