from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.data.database import get_session
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.models.stock import Stock


router = APIRouter(prefix="/api/stocks", tags=["stocks"])


class StockResponse(BaseModel):
    symbol: str
    name: str
    sector: str | None
    market_cap: float | None

    class Config:
        from_attributes = True


@router.get("", response_model=List[StockResponse])
def list_stocks(db: Session = Depends(get_session)) -> List[StockResponse]:
    repo = StockRepository(db)
    stocks = repo.list()
    return [StockResponse.model_validate(s) for s in stocks]


@router.get("/{symbol}", response_model=StockResponse)
def get_stock(symbol: str, db: Session = Depends(get_session)) -> StockResponse:
    repo = StockRepository(db)
    stock: Stock | None = repo.get(symbol)
    if stock is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": True,
                "error_type": "NotFoundError",
                "message": "Stock not found",
            },
        )
    return StockResponse.model_validate(stock)
