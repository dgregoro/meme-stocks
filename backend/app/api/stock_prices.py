"""Stock OHLCV API routes (under /api/stocks)."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.data.database import get_session
from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.utils.stock_helpers import require_stock

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


class PricePointResponse(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int

    model_config = ConfigDict(from_attributes=True)


@router.get("/{symbol}/prices", response_model=List[PricePointResponse])
def get_stock_prices(symbol: str, db: Session = Depends(get_session)) -> List[PricePointResponse]:
    """Get OHLCV price history for a stock."""
    require_stock(db, symbol)
    price_repo = PriceDataRepository(db)
    prices = price_repo.list_for_stock(symbol)
    return [
        PricePointResponse(
            date=p.date.isoformat(),
            open=p.open,
            high=p.high,
            low=p.low,
            close=p.close,
            volume=p.volume,
        )
        for p in prices
    ]
