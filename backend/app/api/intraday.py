"""Intraday minute-bar status and control API."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.config import get_settings

router = APIRouter(prefix="/api/intraday", tags=["intraday"])


class IntradayStatusResponse(BaseModel):
    """Status of intraday ingestion and Alpaca free-plan settings."""

    alpaca_feed: str
    free_plan_mode: bool
    sip_delay_minutes: int
    end_time_safety_minutes: int
    effective_data_lag_minutes: int
    notes: str


@router.get("/status", response_model=IntradayStatusResponse)
def get_intraday_status() -> IntradayStatusResponse:
    """Return Alpaca feed and safety window settings so the limitation is visible without reading code."""
    settings = get_settings()
    safety = settings.alpaca_end_time_safety_minutes
    sip_delay = settings.alpaca_sip_delay_minutes
    effective_lag = max(safety, sip_delay)
    notes = (
        f"Using delayed SIP; ingestion ends at now - {safety} minutes to avoid free-plan 15-minute restriction."
        if settings.alpaca_free_plan_mode
        else "Free plan mode disabled; end time = now."
    )
    return IntradayStatusResponse(
        alpaca_feed=settings.alpaca_data_feed,
        free_plan_mode=settings.alpaca_free_plan_mode,
        sip_delay_minutes=sip_delay,
        end_time_safety_minutes=safety,
        effective_data_lag_minutes=effective_lag,
        notes=notes,
    )
