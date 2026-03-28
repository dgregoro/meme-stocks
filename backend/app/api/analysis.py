from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.data.database import get_session
from backend.app.data.repositories.reddit_symbol_mention_repo import RedditSymbolMentionRepository
from backend.app.services.analysis_service import run_daily_analysis
from backend.app.services.causal_dataset_builder import Freq, build_dataset
from backend.app.services.causal_relationships_service import (
    InsufficientDataResult,
    run_causal_analysis,
)
from backend.app.utils.api_errors import error_detail
from backend.app.utils.stock_helpers import require_stock


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


# --- Causal / lead-lag evidence ---


class LagCorrelationResponse(BaseModel):
    lag: int
    corr: float
    n: int


class PredictiveResultResponse(BaseModel):
    metric: str
    value: float


class PlaceboResultResponse(BaseModel):
    metric: str
    value: float


class CausalEvidenceApiResponse(BaseModel):
    """Lead-lag evidence (not proven causality)."""

    symbol: str
    freq: str
    start_utc: str
    end_utc: str
    sample_size: int
    mention_xcorr: List[LagCorrelationResponse]
    sentiment_xcorr: List[LagCorrelationResponse]
    predictive: List[PredictiveResultResponse]
    placebo: List[PlaceboResultResponse]
    notes: List[str] = []


class InsufficientDataApiResponse(BaseModel):
    """Returned when insufficient data for analysis."""

    symbol: str
    freq: str
    reason: str
    buckets_available: int
    min_required: int
    notes: List[str] = []


@router.get(
    "/causal/{symbol}",
    response_model=CausalEvidenceApiResponse | InsufficientDataApiResponse,
)
def get_causal_evidence(
    symbol: str,
    db: Session = Depends(get_session),
    days: int = Query(default=30, ge=1, le=365, description="Lookback days"),
    freq: str = Query(default="1h", description="Bucket frequency: 15min, 1h, 1d"),
    max_lag: int = Query(default=12, ge=1, le=48),
    include_placebo: bool = Query(default=True),
) -> CausalEvidenceApiResponse | InsufficientDataApiResponse:
    """Get lead-lag evidence: do Reddit mentions/sentiment lead price moves?

    Returns cross-correlation by lag, predictive regression metrics, and placebo test.
    Labeled as evidence, not proven causality.
    """
    require_stock(db, symbol)

    if freq not in ("15min", "1h", "1d"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail(
                "ValidationError",
                f"freq must be 15min, 1h, or 1d; got {freq!r}",
            ),
        )

    settings = get_settings()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    mention_repo = RedditSymbolMentionRepository(db)
    mentions = mention_repo.get_posts_for_symbol(symbol, since=start)
    posts = [m.post for m in mentions]

    dataset_or_err = build_dataset(
        symbol=symbol,
        start=start,
        end=end,
        freq=cast(Freq, freq),
        posts=posts,
        parquet_root=settings.intraday_feature_store_root,
    )

    result = run_causal_analysis(
        dataset_or_error=dataset_or_err,
        max_lag=max_lag,
        include_placebo=include_placebo,
    )

    if isinstance(result, InsufficientDataResult):
        return InsufficientDataApiResponse(
            symbol=result.symbol,
            freq=result.freq,
            reason=result.reason,
            buckets_available=result.buckets_available,
            min_required=result.min_required,
            notes=result.notes,
        )

    return CausalEvidenceApiResponse(
        symbol=result.symbol,
        freq=result.freq,
        start_utc=result.start_utc,
        end_utc=result.end_utc,
        sample_size=result.sample_size,
        mention_xcorr=[LagCorrelationResponse(lag=lc.lag, corr=lc.corr, n=lc.n) for lc in result.mention_xcorr],
        sentiment_xcorr=[LagCorrelationResponse(lag=lc.lag, corr=lc.corr, n=lc.n) for lc in result.sentiment_xcorr],
        predictive=[PredictiveResultResponse(metric=p.metric, value=p.value) for p in result.predictive],
        placebo=[PlaceboResultResponse(metric=p.metric, value=p.value) for p in result.placebo],
        notes=result.notes,
    )
