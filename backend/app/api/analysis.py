from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.data.database import get_session
from backend.app.services.analysis_service import run_daily_analysis


router = APIRouter(prefix="/api/analysis", tags=["analysis"])


class StockAnalysisResponse(BaseModel):
    symbol: str
    sentiment_score: float | None
    mention_count: int
    price_trend: str
    composite_score: float
    rsi: float | None = None
    rsi_signal: str | None = None


@router.get("/daily", response_model=List[StockAnalysisResponse])
def get_daily_analysis(
    db: Session = Depends(get_session),
) -> List[StockAnalysisResponse]:
    """Get daily analysis: stocks ranked by composite score (sentiment + price trend)."""
    rows = run_daily_analysis(db)
    return [
        StockAnalysisResponse(
            symbol=r.symbol,
            sentiment_score=r.sentiment_score,
            mention_count=r.mention_count,
            price_trend=r.price_trend,
            composite_score=r.composite_score,
            rsi=r.rsi,
            rsi_signal=r.rsi_signal,
        )
        for r in rows
    ]
