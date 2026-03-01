"""Intraday minute-bar ingestion using Alpaca with free-plan-safe end times.

Uses compute_safe_end_time so we never query the last ~15 minutes when on
delayed SIP (free plan). All timestamps UTC.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from backend.app.clients.alpaca_data_client import AlpacaDataClient
from backend.app.config import get_settings

logger = logging.getLogger(__name__)


def run_intraday_ingestion(
    symbol: str,
    start: datetime | None = None,
) -> dict[str, int | str]:
    """Fetch minute bars for a symbol, respecting the Alpaca free-plan safety window.

    Args:
        symbol: Ticker symbol.
        start: Optional start of window (UTC). If None, uses end - 1 day.

    Returns:
        Dict with keys like bars_fetched, skipped_reason, etc.
    """
    settings = get_settings()
    client = AlpacaDataClient(
        free_plan_mode=settings.alpaca_free_plan_mode,
        end_time_safety_minutes=settings.alpaca_end_time_safety_minutes,
        feed=settings.alpaca_data_feed,
    )
    now = datetime.now(timezone.utc)
    end = client.compute_safe_end_time(now)

    if start is None:
        start = end - timedelta(days=1)
    start = min(start, end - timedelta(minutes=1))

    if end <= start:
        logger.info(
            "Intraday ingestion skipped for %s: end <= start (end=%s, start=%s)",
            symbol,
            end.isoformat(),
            start.isoformat(),
        )
        return {"bars_fetched": 0, "skipped_reason": "end <= start"}

    bars = client.get_minute_bars(symbol, start, end)
    return {"bars_fetched": len(bars), "symbol": symbol}
