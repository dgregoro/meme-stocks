from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.data.database import get_session
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.utils.api_errors import error_detail
from backend.app.models.stock import Stock
from backend.app.utils.errors import DataAccessError


router = APIRouter(prefix="/api/stocks", tags=["stocks"])


class StockResponse(BaseModel):
    symbol: str
    name: str
    sector: str | None
    market_cap: float | None

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=List[StockResponse])
def list_stocks(db: Session = Depends(get_session)) -> List[StockResponse]:
    """List all tracked stocks."""
    repo = StockRepository(db)
    stocks = repo.list()
    return [StockResponse.model_validate(s) for s in stocks]


@router.get("/{symbol}", response_model=StockResponse)
def get_stock(symbol: str, db: Session = Depends(get_session)) -> StockResponse:
    """Get a single stock by symbol. Returns 404 if not found."""
    repo = StockRepository(db)
    stock: Stock | None = repo.get(symbol)
    if stock is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_detail("NotFoundError", "Stock not found"),
        )
    return StockResponse.model_validate(stock)


class CreateStockRequest(BaseModel):
    """Request model for creating a stock."""

    symbol: str
    name: str
    sector: str | None = None
    market_cap: float | None = None


@router.post("", response_model=StockResponse, status_code=status.HTTP_201_CREATED)
def create_stock(req: CreateStockRequest, db: Session = Depends(get_session)) -> StockResponse:
    """Add a new stock to track.

    The stock symbol will be used for ticker extraction from Reddit posts.
    """
    repo = StockRepository(db)

    # Check if stock already exists
    existing = repo.get(req.symbol.upper())
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": True,
                "error_type": "ConflictError",
                "message": f"Stock {req.symbol} already exists",
            },
        )

    try:
        stock = Stock(
            symbol=req.symbol.upper(),
            name=req.name,
            sector=req.sector,
            market_cap=req.market_cap,
        )
        repo.add(stock)
        db.commit()
        return StockResponse.model_validate(stock)
    except DataAccessError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("DataAccessError", str(exc)),
        ) from exc
