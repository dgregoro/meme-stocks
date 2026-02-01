"""Shared helpers for stock-related API logic."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.models.stock import Stock
from backend.app.utils.api_errors import error_detail


def require_stock(db: Session, symbol: str) -> Stock:
    """Return stock by symbol or raise HTTPException 404 if not found."""
    repo = StockRepository(db)
    stock = repo.get(symbol)
    if stock is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_detail("NotFoundError", "Stock not found"),
        )
    return stock
